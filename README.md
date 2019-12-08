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
    ├── lightning-dirs
    ├── py
    └── sh
```

The paths of `lab` and `ln` should be set in the variables `LAB` and `LN` respectively. 
`LN/sh` should be added to `PATH`.

## Where to start
`setup-env` is the recommended entry point. It creates a complete setup of bitcoin and 
lightning nodes ready for interaction. Run `setup-env --help` to see more details and options.


