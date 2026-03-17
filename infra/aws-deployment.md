# AWS Deployment Guide

## Target Stack

- Frontend: Vercel or AWS Amplify (Next.js static + SSR)
- Backend: ECS Fargate (FastAPI)
- Database: RDS PostgreSQL
- Cache/PubSub: ElastiCache Redis
- Network: ALB + ACM + Route53
- Secrets: AWS Secrets Manager
- Observability: CloudWatch + X-Ray

## Steps

1. Provision networking
- Create VPC with private/public subnets.
- Place ECS services in private subnets.
- Use NAT for outbound broker API traffic.

2. Provision data layer
- Create RDS PostgreSQL instance.
- Create ElastiCache Redis cluster.
- Create security groups allowing backend to connect to both.

3. Container registry
- Create ECR repos for backend and frontend.
- Build and push images.

4. ECS service
- Create task definition with env vars from Secrets Manager.
- Run backend service with autoscaling (CPU + memory + request count).
- Expose backend through ALB path `/api/*` and `/docs` (optional auth).

5. Frontend hosting
- Option A: Deploy Next.js in Amplify with env vars.
- Option B: Deploy on ECS behind ALB path `/`.

6. TLS + domain
- Provision ACM cert.
- Attach to ALB listener 443.
- Route53 records for app and api.

7. Observability
- Enable structured logs to CloudWatch.
- Add alarms: HTTP 5xx, p95 latency, container restarts, DB CPU, Redis memory.

8. CI/CD
- GitHub Actions: test -> build -> push ECR -> deploy ECS.

## Runtime Config Checklist

- `SECRET_KEY`
- `ENCRYPTION_KEY`
- `POSTGRES_URL`
- `REDIS_URL`
- `OPENAI_API_KEY`
- Broker credentials (`KITE_*`, `ANGEL_*`, `UPSTOX_*`)
- Alert settings (`TELEGRAM_*`, `SMTP_*`)

## High Availability Recommendations

- Multi-AZ RDS
- Redis replication group
- ECS min 2 tasks across AZs
- ALB health checks and rolling deployments
