import * as cdk from 'aws-cdk-lib/core';
import { Construct } from 'constructs';
import { Storage } from './storage';

export class InfraStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const storage = new Storage(this, 'Storage');

    new cdk.CfnOutput(this, 'BucketName', { value: storage.bucket.bucketName });
  }
}
