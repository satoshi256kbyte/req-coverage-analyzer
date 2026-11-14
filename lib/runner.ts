import * as cdk from 'aws-cdk-lib/core';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';

export interface RunnerProps {
  readonly bucket: s3.IBucket;
  /** 公式の decider の、別名 `live` を含む ARN */
  readonly deciderFunctionArn: string;
  /** decider を同時に呼ぶ本数 */
  readonly concurrency?: number;
}

/** CSV を検証し、decider を呼んで集計し、レポートを書く Lambda。 */
export class Runner extends Construct {
  public readonly function: lambda.Function;

  constructor(scope: Construct, id: string, props: RunnerProps) {
    super(scope, id);

    this.function = new lambda.Function(this, 'Function', {
      runtime: lambda.Runtime.PYTHON_3_14,
      architecture: lambda.Architecture.ARM_64,
      handler: 'req_coverage_runner.handler.lambda_handler',
      code: lambda.Code.fromAsset('src', { exclude: ['**/__pycache__', '**/*.pyc'] }),
      memorySize: 512,
      // 同時に動く実行を、少数に抑える（decider の同時実行と費用を、利用者の入力で増やさない）
      reservedConcurrentExecutions: 5,
      // decider の冷えた読み込み（約5分）と判定を含めて、Lambda の上限の15分
      timeout: cdk.Duration.minutes(15),
      environment: {
        BUCKET_NAME: props.bucket.bucketName,
        DECIDER_FUNCTION_ARN: props.deciderFunctionArn,
        CONCURRENCY: String(props.concurrency ?? 50),
      },
      logGroup: new logs.LogGroup(this, 'Logs', {
        retention: logs.RetentionDays.TWO_WEEKS,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }),
    });

    // 入力の読み取りと、出力の書き込みだけ。決まったフォルダの下に限る。
    // 一覧の権限は、入力の下の指定に限る。これがないと、存在しないキーの読み取りが、
    // 「ない」（NoSuchKey）ではなく「権限がない」（AccessDenied）になる
    this.function.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['s3:GetObject'],
        resources: [props.bucket.arnForObjects('runs/*/input/*')],
      }),
    );
    this.function.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['s3:ListBucket'],
        resources: [props.bucket.bucketArn],
        conditions: { StringLike: { 's3:prefix': ['runs/*/input/*'] } },
      }),
    );
    this.function.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['s3:PutObject'],
        resources: [props.bucket.arnForObjects('runs/*/output/*')],
      }),
    );
    this.function.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['lambda:InvokeFunction'],
        resources: [props.deciderFunctionArn],
      }),
    );
  }
}
