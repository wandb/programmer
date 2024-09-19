# Container Manager Server

## Build images on server

We use this for running swe-bench locally against containers on a remote server. See [swe-bench README](../swe-bench/README.md) for steps to build the SWE-bench images.

## Run and check server

put cmserver.py on remote machine

```
gcloud compute scp --zone "us-west1-a" --project "weave-support-367421" cmserver.py programmer-benchmark2:~/cm/
```

on remote machine

(just 1 worker for now, there's global state)

```
uvicorn cmserver:app --host 0.0.0.0 --port 8000 --workers 1
```

tunnel from local machine to remote

```
gcloud compute ssh --zone "us-west1-a" "programmer-benchmark" --project "weave-support-367421"  -- -NL 8000:localhost:8000
```

local machine

```
python checkserver.py
```

result on remote machine should be there are no more running containers when done
