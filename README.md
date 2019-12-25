# LN

This repo contains a bunch of scripts for interacting with bitcoin and lightning nodes.

The tools in this repo assume the following directory structure:

```
lab
├── bitcoin
│   ├── ...
│   └── ...
├── lightning
│   ├── ...
│   └── ...
├── lightning-evil (a modified impl of c-lightning)
│   ├── ...
│   └── ...
└── ln (this repo)
    ├── conf
    ├── py
    ├── sh
    └── topologies
```

The paths of `lab` and `ln` should be set in the variables `LAB` and `LN` respectively. 
`LN/sh` should be added to `PATH`.

## Where to start
Two main interesting entry points are `setup-env` and `lightning_commands_generator.py`.  
`setup-env` is good for starting an interactive session - it starts all bitcoin/lightning nodes
and create channels, so we can start sending commands. It generates all the required code
using the `lightning_commands_generator.py`.  
`lightning_commands_generator` can generate bash commands to start nodes, open channels, 
make payments between nodes, execute the attack, dump simulation data and more. Its purpose 
is the automate the process of setting up the environment and to easily and quickly simulate
our attacks.
