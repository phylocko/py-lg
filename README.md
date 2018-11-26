# Py-LG

iHome Looking Glass written on Python

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Creating a virtual env

```
mkdir -p venv/py-lg
virtualenv --python=python3 venv/py-lg
source venv/py-lg/bin/activate
```

### Getting the source code

Create project's folder and copy repo data into it:

```
mkdir py-lg
git clone git@gitlab.com:phylocko/py-lg.git py-lg
```

### Installing the requirements

```
pip install -r py-lg/requirements.txt
```

### Adapting the configuration

```
vi py-lg/app.py
```

Edit last line of the file to define your local IP-Address and port.


### Running the LG

Explain what these tests test and why

```
python py-lg/app.py
```
