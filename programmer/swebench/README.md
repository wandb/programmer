# SWE Bench stuff

## Build SWE-bench images

First do setup (below) then run this command to build all the images. --cache_level instance tells the script not to delete the instance images, which are what we want to use with container-manager.

```
python -m swebench.harness.run_evaluation \
     --predictions_path gold \
     --max_workers 24 \
     --run_id validate-gold \
     --dataset_name princeton-nlp/SWE-bench_Verified \
     --cache_level instance
```


## remote machine setup instructions on gcp VM ubuntu 20.04

```

sudo snap install docker
sudo groupadd docker
sudo usermod -aG docker $USER
sudo chown root:docker /var/run/docker.sock
sudo chmod 660 /var/run/docker.sock

sudo apt update
sudo apt install -y \
    build-essential \
    libbz2-dev \
    libreadline-dev \
    libssl-dev \
    zlib1g-dev \
    libsqlite3-dev \
    libffi-dev \
    libncursesw5-dev \
    libgdbm-dev \
    liblzma-dev \
    tk-dev \
    libdb-dev \
    libexpat1-dev \
    libmpdec-dev \
    libxml2-dev \
    libxmlsec1-dev \
    libffi-dev \
    liblzma-dev

# pyenv
curl https://pyenv.run | bash
echo 'export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"' >> ~/.bashrc
## exit and re-log in

pyenv install 3.10.12
pyenv virtualenv 3.10.12 swe-bench

git clone https://github.com/princeton-nlp/SWE-bench.git
cd SWE-bench
pyenv local swe-bench
pip install -e .
```