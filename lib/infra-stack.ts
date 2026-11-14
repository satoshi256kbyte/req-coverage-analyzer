import * as cdk from 'aws-cdk-lib/core';
import { Construct } from 'constructs';
import { Runner } from './runner';
import { Storage } from './storage';

export class InfraStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const deciderFunctionArn = this.node.tryGetContext('deciderFunctionArn');
    if (typeof deciderFunctionArn !== 'string' || deciderFunctionArn === '') {
      throw new Error('コンテキスト deciderFunctionArn（decider の別名 live の ARN）を指定してください: -c deciderFunctionArn=<ARN>');
    }

    const storage = new Storage(this, 'Storage');
    const runner = new Runner(this, 'Runner', { bucket: storage.bucket, deciderFunctionArn });

    new cdk.CfnOutput(this, 'BucketName', { value: storage.bucket.bucketName });
    new cdk.CfnOutput(this, 'RunnerFunctionName', { value: runner.function.functionName });
  }
}
