import { DeleteObjectCommand, HeadBucketCommand, PutObjectCommand, S3Client } from "@aws-sdk/client-s3";
import fs from "node:fs";
import { env } from "../env";

function client(region?: string): S3Client {
  if (!env.awsAccessKeyId || !env.awsSecretAccessKey) {
    throw new Error("AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY are not configured.");
  }
  return new S3Client({
    region: region ?? env.awsRegion ?? "us-east-1",
    credentials: { accessKeyId: env.awsAccessKeyId, secretAccessKey: env.awsSecretAccessKey },
  });
}

export interface UploadResult {
  bucket: string;
  key: string;
  url: string;
}

export async function uploadFile(
  bucket: string,
  key: string,
  localPath: string,
  contentType: string,
  region?: string
): Promise<UploadResult> {
  const s3 = client(region);
  const body = fs.createReadStream(localPath);
  await s3.send(new PutObjectCommand({ Bucket: bucket, Key: key, Body: body, ContentType: contentType }));
  const resolvedRegion = region ?? env.awsRegion ?? "us-east-1";
  return { bucket, key, url: `https://${bucket}.s3.${resolvedRegion}.amazonaws.com/${key}` };
}

/**
 * Diagnostics "Test Connection": HeadBucket alone only proves the bucket exists and is
 * reachable — it does not prove the credentials can actually write to it (a read-only policy
 * would pass HeadBucket and then fail every real upload). This additionally writes and deletes
 * a small marker object so a green result means uploads will really work.
 */
export async function testAwsConnection(bucket: string, region?: string): Promise<{ ok: boolean; message: string }> {
  try {
    const s3 = client(region);
    await s3.send(new HeadBucketCommand({ Bucket: bucket }));
    const testKey = `.victory-connection-test/${Date.now()}.txt`;
    await s3.send(new PutObjectCommand({ Bucket: bucket, Key: testKey, Body: "connection test", ContentType: "text/plain" }));
    await s3.send(new DeleteObjectCommand({ Bucket: bucket, Key: testKey }));
    return { ok: true, message: `Connected. Bucket "${bucket}" is reachable and writable.` };
  } catch (err) {
    return { ok: false, message: err instanceof Error ? err.message : String(err) };
  }
}
