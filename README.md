# Lightning Systemic Attack

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
│   ├── eclair-node
│   ├── lightning-cli
│   ├── lightningd
│   ├── lightningd-evil (a modified impl of c-lightning)
│   ├── lncli
│   └── lnd
├── conf (bitcoin/lightning conf files)
├── data (extracted data from lightning's mainnet)
├── py (python code)
├── sh (useful bash scripts)
├── simulations (full simulation script examples)
└── topologies (useful topology files. see commands_generator for more info)
```

*Note: the `bin` directory is not part of this repo and should be created by the user. The existence of 
the `bin` directory and its content is assumed by some of the code (specifically, the `commands_generator`. see below)*

Before starting you should set the following things:
1. The full path of the root dir `ln` is set in the bash variable named `LN`
2. `LN/bin` and `LN/sh` are added to `PATH`
3. `LN/bin` contains the executables (or links to them) as specified in the tree above

You can add these lines into your .bashrc
```
export LN="$HOME/lightning-systemic-attack"
PATH="$LN/sh:$LN/bin:$PATH"
```

## Where to start
The main entry point is probably the `commands_generator` module. It is responsible for generating
simulations scripts, which include setting up nodes (lightning+bitcoin), open channels, 
routing payments, execute the attack, dump simulation data and more.
Any python code should be run from the root directory `py`.
For more details on how to use the `commands_generator` use the help menu:
```
python3 -m commands_generator.commands_generator --help
```


## Nodes version
The latest bitcoin/lightning versions that were tested and work with our code:

| Implementation| Version  |
|---------------|----------|
| bitcoin-core  | 0.19.0.1 |
| c-lightning   | 0.8.1    |
| lnd           | 0.9.2    |
| eclair        | 0.4      |
