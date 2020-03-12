# LN

This repository contains code for running and manipulating bitcoin and lightning nodes.
It was created to support a proposed attack on Bitcoin's Lightning Network.


## Project Structure
This repo is organized in the following way

```
ln
├── bin
│   ├── bitcoin-cli
│   ├── bitcoind
│   ├── eclair-cli
│   ├── eclair.jar
│   ├── lightning-cli
│   ├── lightningd
│   ├── lightningd-evil (a modified impl of c-lightning)
│   ├── lncli
│   └── lnd
├── conf (bitcoin/lightning conf files)
├── py (python code)
├── sh (bash scripts)
├── simulations (full simulation script examples)
└── topologies (useful topology files. see commands_generator for more info)
```

*Note: the `bin` directory is not part of this repo and should be created by the user. The existence of 
the `bin` directory and its content is assumed by some of the code (specifically, the `commands_generator`. see below)*

Before starting you should set the following things:
1. The full path of the root dir `ln` is set in the bash variable named `LN`
2. `LN/bin` and `LN/sh` are added to `PATH`
3. `LN/bin` contains the executables (or links to them) as specified in the tree above


## Where to start
Two main interesting entry points are `setup-env` and `commands_generator.py`.  
`setup-env` is good for starting an interactive session - it starts bitcoin+lightning nodes
and create channels, so we can quickly start interacting with the nodes. It generates all the required code
using the `commands_generator`.  
`commands_generator` can generate bash commands to start nodes, open channels, 
make payments between nodes, execute the attack, dump simulation data and more. Its purpose 
is the automate the process of setting up the environment and to easily and quickly simulate
our attack. You can see a usage of the `commands_generator` in the simulation scripts, under the `simulations` directory.


## Nodes version
The latest bitcoin/lightning versions that were tested and work with our code:

| Implementation| Version  |
|---------------|----------|
| bitcoin-core  | 0.19.0.1 |
| c-lightning   | 0.8.0    |
| lnd           | 0.8.2    |
| eclair        | 0.3.3    |
