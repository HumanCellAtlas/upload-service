# HCA Staging System

## Setup

Do this once:

```bash
cp config/environment.dev.example config/environment.dev
```

## Testing

```bash
source config/environment
make test
```

## Deployment

e.g. to manually deploy to staging:

```bash
DEPLOYMENT_STAGE=staging
source config/environment
make deploy
```
