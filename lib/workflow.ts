import * as cdk from 'aws-cdk-lib/core';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import { Construct } from 'constructs';

export interface WorkflowProps {
  readonly bucket: s3.IBucket;
  readonly runner: lambda.IFunction;
}

/** 入力が揃うのを待ち、runner を呼び、失敗なら FAILED.json を書く Step Functions。 */
export class Workflow extends Construct {
  public readonly stateMachine: sfn.StateMachine;

  constructor(scope: Construct, id: string, props: WorkflowProps) {
    super(scope, id);
    const { bucket, runner } = props;
    const runId = sfn.JsonPath.stringAt('$.run_id');

    // 1. EventBridge のイベント（S3 の Object Created）から、run-id を取り出す。
    //    キーは `runs/<run-id>/input/<name>`
    const extract = new sfn.Pass(this, 'ExtractRunId', {
      parameters: {
        run_id: sfn.JsonPath.arrayGetItem(sfn.JsonPath.stringSplit(sfn.JsonPath.stringAt('$.detail.object.key'), '/'), 1),
      },
    });

    // 2. 実行の印を、条件つきで書く。すでにあれば、別の実行が担当しているので、何もせずに終わる
    const claim = new tasks.CallAwsService(this, 'Claim', {
      service: 's3',
      action: 'putObject',
      parameters: {
        Bucket: bucket.bucketName,
        Key: sfn.JsonPath.format('runs/{}/state/claimed', runId),
        Body: 'claimed',
        IfNoneMatch: '*',
      },
      iamResources: [bucket.arnForObjects('runs/*/state/claimed')],
      iamAction: 's3:PutObject',
      resultPath: sfn.JsonPath.DISCARD,
    });
    const alreadyClaimed = new sfn.Succeed(this, 'AlreadyClaimed');
    const claimFailed = new sfn.Fail(this, 'ClaimFailed', { error: 'ClaimFailed', cause: '実行の印を書けませんでした' });
    claim.addCatch(
      new sfn.Choice(this, 'IsAlreadyClaimed')
        .when(
          sfn.Condition.or(
            sfn.Condition.stringMatches('$.error.Cause', '*PreconditionFailed*'),
            sfn.Condition.stringMatches('$.error.Cause', '*Status Code: 412*'),
          ),
          alreadyClaimed,
        )
        .otherwise(claimFailed),
      { errors: ['States.ALL'], resultPath: '$.error' },
    );

    // 3. input/ に2つのファイルが揃うまで、30秒おきに最大20回（10分）待つ
    const initAttempt = new sfn.Pass(this, 'InitAttempt', {
      parameters: { run_id: runId, attempt: 0 },
    });
    const listInputs = new tasks.CallAwsService(this, 'ListInputs', {
      service: 's3',
      action: 'listObjectsV2',
      parameters: {
        Bucket: bucket.bucketName,
        Prefix: sfn.JsonPath.format('runs/{}/input/', runId),
      },
      iamResources: [bucket.bucketArn],
      iamAction: 's3:ListBucket',
      resultPath: '$.list',
    });
    const wait = new sfn.Wait(this, 'WaitForInputs', { time: sfn.WaitTime.duration(cdk.Duration.seconds(30)) });
    const nextAttempt = new sfn.Pass(this, 'NextAttempt', {
      parameters: {
        run_id: runId,
        attempt: sfn.JsonPath.mathAdd(sfn.JsonPath.numberAt('$.attempt'), 1),
      },
    });

    // 4. runner を呼ぶ
    const run = new tasks.LambdaInvoke(this, 'RunRunner', {
      lambdaFunction: runner,
      payload: sfn.TaskInput.fromObject({ run_id: runId }),
      resultPath: '$.result',
      retryOnServiceExceptions: false,
    });

    // 5. 失敗: failure を作り、FAILED.json を書いて、実行を失敗で終える
    const failure = (id: string, errorCode: string | undefined, message: string | undefined) =>
      new sfn.Pass(this, id, {
        parameters: {
          run_id: runId,
          failure: {
            run_id: runId,
            error_code: errorCode ?? sfn.JsonPath.stringAt('$.result.Payload.error_code'),
            message: message ?? sfn.JsonPath.stringAt('$.result.Payload.message'),
            failed_at: sfn.JsonPath.stringAt('$$.State.EnteredTime'),
          },
        },
      });
    const inputTimeout = failure('InputTimeout', 'input_timeout', '2つの CSV が10分以内に揃いませんでした');
    const runnerFailed = failure('RunnerFailed', undefined, undefined);
    const runnerTimeout = failure('RunnerTimeout', 'runner_timeout', '判定の処理が上限の時間を超えました');
    const internalError = failure('InternalError', 'internal_error', '想定外のエラーです。ログを確認してください');

    const writeFailed = new tasks.CallAwsService(this, 'WriteFailed', {
      service: 's3',
      action: 'putObject',
      parameters: {
        Bucket: bucket.bucketName,
        Key: sfn.JsonPath.format('runs/{}/output/FAILED.json', runId),
        Body: sfn.JsonPath.jsonToString(sfn.JsonPath.objectAt('$.failure')),
        ContentType: 'application/json',
      },
      iamResources: [bucket.arnForObjects('runs/*/output/FAILED.json')],
      iamAction: 's3:PutObject',
      resultPath: sfn.JsonPath.DISCARD,
    });
    const runFailed = new sfn.Fail(this, 'RunFailed', { error: 'RunFailed', cause: 'FAILED.json を書きました' });
    inputTimeout.next(writeFailed);
    runnerFailed.next(writeFailed);
    runnerTimeout.next(writeFailed);
    internalError.next(writeFailed);
    writeFailed.next(runFailed);

    run.addCatch(
      new sfn.Choice(this, 'IsRunnerTimeout')
        .when(sfn.Condition.stringMatches('$.error.Cause', '*timed out*'), runnerTimeout)
        .otherwise(internalError),
      { errors: ['States.ALL'], resultPath: '$.error' },
    );
    const done = new sfn.Succeed(this, 'Succeeded');
    const afterRun = new sfn.Choice(this, 'RunnerResult')
      .when(sfn.Condition.stringEquals('$.result.Payload.status', 'succeeded'), done)
      .when(sfn.Condition.stringEquals('$.result.Payload.status', 'failed'), runnerFailed)
      .otherwise(internalError);
    run.next(afterRun);

    const ready = new sfn.Choice(this, 'InputsReady')
      .when(sfn.Condition.isPresent('$.list.Contents[1]'), run)
      .when(sfn.Condition.numberGreaterThanEquals('$.attempt', 20), inputTimeout)
      .otherwise(wait);
    wait.next(nextAttempt);
    nextAttempt.next(listInputs);
    listInputs.next(ready);

    this.stateMachine = new sfn.StateMachine(this, 'StateMachine', {
      definitionBody: sfn.DefinitionBody.fromChainable(extract.next(claim).next(initAttempt).next(listInputs)),
      // 入力の待ち（最大10分）と runner（最大15分）に、余裕を足した全体の上限
      timeout: cdk.Duration.minutes(30),
    });

    // 入力の CSV が置かれたら、Step Functions を起動する（2つのファイルで、それぞれ1回）。
    // 重複した起動は、Claim の状態で取り除く
    new events.Rule(this, 'InputCreated', {
      description: 'runs/<run-id>/input/ に、要件かE2Eテストの CSV が置かれたら、判定を始める',
      eventPattern: {
        source: ['aws.s3'],
        detailType: ['Object Created'],
        detail: {
          bucket: { name: [bucket.bucketName] },
          object: {
            key: [{ wildcard: 'runs/*/input/requirements.csv' }, { wildcard: 'runs/*/input/e2e-tests.csv' }],
          },
        },
      },
      targets: [new targets.SfnStateMachine(this.stateMachine)],
    });
  }
}
