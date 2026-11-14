import * as cdk from 'aws-cdk-lib/core';
import { Construct } from 'constructs';
import { Runner } from './runner';
import { Storage } from './storage';
import { Workflow } from './workflow';

export class InfraStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const deciderFunctionArn = this.node.tryGetContext('deciderFunctionArn');
    if (typeof deciderFunctionArn !== 'string' || deciderFunctionArn === '') {
      throw new Error('コンテキスト deciderFunctionArn（decider の別名 live の ARN）を指定してください: -c deciderFunctionArn=<ARN>');
    }

    const storage = new Storage(this, 'Storage');
    const runner = new Runner(this, 'Runner', { bucket: storage.bucket, deciderFunctionArn });

    const workflow = new Workflow(this, 'Workflow', { bucket: storage.bucket, runner: runner.function });

    new cdk.CfnOutput(this, 'BucketName', { value: storage.bucket.bucketName });
    new cdk.CfnOutput(this, 'RunnerFunctionName', { value: runner.function.functionName });
    new cdk.CfnOutput(this, 'StateMachineArn', { value: workflow.stateMachine.stateMachineArn });
  }
}
