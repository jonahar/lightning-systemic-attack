# ln

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
└── ln (this repo)
    ├── conf
    ├── dev
    ├── lightning-dirs
    ├── py
    └── sh
```

The paths of `lab` and `ln` should be set in the variables `LAB` and `LNPATH` respectively, 
and `LNPATH/sh` should be added to `PATH`

