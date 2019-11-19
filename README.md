# Py-LG

Looking Glass for internet IX with Bird written on Python

## Getting Started

These instructions will get you a copy of the project up and running 
on your local machine for development and testing purposes.

### Create a virtual env

```
mkdir -p venv/py-lg
virtualenv --python=python3 venv/py-lg
source venv/py-lg/bin/activate
```

### Get the source code

```
mkdir py-lg
git clone git@gitlab.com:phylocko/py-lg.git py-lg
```

### Installing the requirements

```
pip install -r py-lg/requirements.txt
```

### Edit the configuration file

```
cp py-lg/config_example.py py-lg/config.py
vi py-lg/config.py
```

### Run the developer's LG

```
python py-lg/app.py
```
