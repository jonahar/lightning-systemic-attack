from binascii import hexlify, unhexlify
from typing import List, Optional

from bitcoin.core.script import CScript, CScriptOp

HTLC_SCRIPT_TOKENS = [
    "OP_DUP",
    "OP_HASH160",
    None,  # <RIPEMD160(SHA256(revocationpubkey))>
    "OP_EQUAL",
    "OP_IF",
    "OP_CHECKSIG",
    "OP_ELSE",
    None,  # <remote_htlcpubkey>
    "OP_SWAP",
    "OP_SIZE",
    "32",
    "OP_EQUAL",
    "OP_IF",
    "OP_HASH160",
    None,  # <RIPEMD160(payment_hash)>
    "OP_EQUALVERIFY",
    "2",
    "OP_SWAP",
    None,  # <local_htlcpubkey>
    "2",
    "OP_CHECKMULTISIG",
    "OP_ELSE",
    "OP_DROP",
    None,  # <cltv_expiry>
    "OP_CHECKLOCKTIMEVERIFY",
    "OP_DROP",
    "OP_CHECKSIG",
    "OP_ENDIF",
    "OP_ENDIF",
]


def decode_script(script_hex: str) -> List[str]:
    ops = list(CScript(unhexlify(script_hex)))
    ops_str: List[str] = []
    for op in ops:
        if type(op) == CScriptOp or type(op) == int:
            ops_str.append(str(op))
        elif type(op) == bytes:
            num = int.from_bytes(op, byteorder="little")
            if num < 1_000_000:
                # this is a small number. probably represents a height/expiration/etc.
                # rather than some cryptographic key. convert it to decimal
                ops_str.append(str(num))
            else:
                # append it as hex
                ops_str.append(hexlify(op).decode("utf8"))
        else:
            raise ValueError(f"Unrecognized script op: {op}")
    return ops_str


def is_htlc_script(script_hex: str) -> bool:
    tokens = decode_script(script_hex)
    if len(tokens) != len(HTLC_SCRIPT_TOKENS):
        return False
    
    return all(
        HTLC_SCRIPT_TOKENS[i] is None
        or
        tokens[i] == HTLC_SCRIPT_TOKENS[i]
        or
        (HTLC_SCRIPT_TOKENS[i] == "OP_CHECKLOCKTIMEVERIFY" and tokens[i] == "OP_NOP2")
        for i in range(len(tokens))
    )


def get_htlc_expiration_height(script_hex: str) -> Optional[int]:
    if not is_htlc_script(script_hex):
        raise ValueError("not a valid htlc script")
    return int(decode_script(script_hex)[23])
