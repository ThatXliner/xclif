# Greeter

An over-engineered hello world CLI built using Xclif.

## Usage

```
python -m greeter greet [--name <name>] [--template <template>]
python -m greeter config set [--name <name>] [--template <template>]
python -m greeter config get
```

## Examples

```
python -m greeter greet --name Alice
# Hello, Alice!

python -m greeter greet --name Alice --template "Hi there, {}!"
# Hi there, Alice!

python -m greeter config set --name Bob --template "Hey, {}!"
python -m greeter greet
# Hey, Bob!
```
