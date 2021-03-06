# -*- coding: utf-8 -*-

from __future__ import print_function

"""
LELEC2770 : Privacy Enhancing Technologies

Exercice Session : Secure 2-party computation

Garbled Circuit
"""

import six
from Crypto.Random import random
import Crypto.Util.number

import OT
from aes import AES_key
from logic_circuit import Gate


def garble_circuit(circuit, myinputs):
    """Garble a circuit

    :param circuit: circuit to garble
    :type circuit: logic_circuit.Circuit
    :param myinputs: already known inputs, to be hidden
    :type myinputs: dictionnary {gate_id: 0/1}
    :return: Garbled circuit, ungarbling keys associated to myinputs and OT
        senders for other inputs.
    :rtype: (garbled_table, input_keys, ot_senders)

    - garbled_table: dictionnary {gate_id: 4*[AES_key]}
    - input_keys: dictionnary {input_gate_id: AES_key}
    - ot_senders: dictionnary {input_gate_id: OT.Sender}
    """
    # @students: What are the key steps in this function that make it such that
    #             the inputs of Alice are not revealed to Bob ?
    
    # Garbling keys (k_0, k_1) for each gate => secret
    output_table = {}
    # Garbled table for each gate => public
    garbled_table = {}
    # Ungarbling keys associated to my inputs => public
    input_keys = {}
    # OT senders for inputs of the other guy => public
    ot_senders = {}

    # ---- Input validation ----
    for g_id, g_value in six.iteritems(myinputs):
        assert circuit.g[g_id].kind == "INPUT"
        assert g_value in (0, 1)

    # ---- Garbling keys generation ----
    for g_id in circuit.g:
        # For output gates, we encrypt the binary output instead of an AES key.
        if not g_id in circuit.output_gates:
            k_0 = AES_key.gen_random()
            k_1 = AES_key.gen_random()
            output_table[g_id] = (k_0, k_1)

    # ---- Garbled tables generation ----
    for g_id, gate in six.iteritems(circuit.g):
        # We already retrieved the values for all the input gates.
        if gate.kind != "INPUT":
            K_0 = output_table[gate.in0_id]  # K_0 = k_00, k_01
            K_1 = output_table[gate.in1_id]  # K_1 = k_10, k_11
            c_list = []
            for i in range(2):
                for j in range(2):
                    # 'real' evaluation of the gate on i,j
                    alpha = Gate.compute_gate(gate.kind, i, j)
                    if g_id in circuit.output_gates:
                        m = _encode_int(alpha)  # 0 or 1
                    else:
                        K = output_table[g_id]
                        m = _encode_key(K[alpha])  # k_0 or k_1 (see above)
                    c = K_1[j].encrypt(m)
                    c_ij = K_0[i].encrypt(c)
                    c_list.append(c_ij)
            # @students: Why is it important to shuffle the list?
            # ANSWER: to avoid leaking keys due to the ordering of c_ij's (the
            #          Garbled Circuit Table values)
            random.shuffle(c_list)
            garbled_table[g_id] = c_list

    # ---- Ungarbling keys generation for my inputs ----
    for g_id, input_val in six.iteritems(myinputs):
        K = output_table[g_id]
        key = K[input_val]  # key = K[i] where i in [0,1] is my input
        input_keys[g_id] = key

    # ---- Oblivious transfer senders ----
    for g_id, gate in six.iteritems(circuit.g):
        if gate.kind == "INPUT" and g_id not in myinputs:
            k0, k1 = output_table[g_id]
            ot_senders[g_id] = OT.Sender(k0, k1)
    return (garbled_table, input_keys, ot_senders)


def evaluate_garbled_circuit(circuit, myinputs, garbled_table, input_keys, ot_senders):
    """Evaluate a garbled circuit

    :param circuit: circuit to evaluate
    :type circuit: lib.logic_circuit.Circuit
    :param myinputs: known inputs, to be kept hidden
    :type myinputs: dictionnary {gate_id: 0/1}
    :param garbled_table: Table of garbled logic gates
    :type garbled_table: dictionnary {gate_id: 4*[AES_key]}
    :param input_keys: ungarbling keys already known
    :type input_keys: dictionnary {input_gate_id: AES_key}
    :param ot_senders: OT senders to recover missing input keys using myinputs
                        values
    :return: State of the evaluated circuit
    :rtype: dictionnary {gate_id: gate_output_value}
    """
    # @students: What are the key steps in this function that make it such that
    #             the inputs of Bob are not revealed to Alice ?
    state = input_keys.copy()
    # ---- Input validation ----
    for g_id, g_value in six.iteritems(myinputs):
        assert circuit.g[g_id].kind == "INPUT"
        assert g_value in (0, 1)
    assert set(ot_senders) == set(myinputs)

    # **************************************************************************
    # ---- make OTs, store resulting keys in state ----
    # <to be completed by students>
    for i, b in myinputs.items():
        Bob = OT.Receiver()
        pk, c = Bob.pk, Bob.challenge(b)
        c_0, c_1 = ot_senders[i].response(c, pk)
        state[i] = Bob.decrypt_response(c_0, c_1, b)
    # </to be completed by students>
    # **************************************************************************

    # ---- Recursive ungarbling ----
    def _evaluate_garbled_gate_rec(g_id):
        # **********************************************************************
        # Exercise 2
        # ==========
        # (b) Complete this part of the function.
        # <to be completed by students>
        #  when evaluating a gate, make a shortcut variable first
        gate = circuit.g[g_id]
        #  if gate's inputs are not already evaluated, recursively do so
        if gate.in0_id not in state:
            _evaluate_garbled_gate_rec(gate.in0_id)
        if gate.in1_id not in state:
            _evaluate_garbled_gate_rec(gate.in1_id)
        # now that inputs are evaluated, get their related keys from the state
        key0 = state[gate.in0_id]
        key1 = state[gate.in1_id]
        # and decrypt each line from the received GCT up to the decodable one
        #  (others could not be decoded as only one set of input keys works)
        for line in garbled_table[g_id]:
            decoded_line = _decode_decryption(key1.decrypt(key0.decrypt(line)))
            if decoded_line is not None:
                # at this point, if decoded_line is an AES key, it means that
                #  there are still gates behind to be evaluated :
                # if decoded_line is an integer, then we reached the end of the
                #  circuit
                state[g_id] = decoded_line
        # </to be completed by students>
        # **********************************************************************

    for g_id in circuit.output_gates:
        _evaluate_garbled_gate_rec(g_id)

    return state


# ******************************************************************************
# Exercise 2
# ==========
# (a) When decrypting the garbled table for a logic gate, how does one know 
#      that a decryption is correct ?
# ANSWER: the decryption is incorrect when the decrypted value of
#          _decode_decryption(d) does not hold a marker indicating its type in
#          the 16 trailing bytes (see branch with 'return None' hereafter) ;
#         i.e. when decrypting a bad line from the Garbled Circuit Table (GCT)
#          (cfr only one GCT line will decrypt correctly given the input keys)
# ******************************************************************************

INT_MARKER = 15*b'\x00' + b'\x01'
KEY_MARKER = 16*b'\x00'

def _encode_int(x):
    """Encode integer before encryption"""
    return Crypto.Util.number.long_to_bytes(x, 16) + INT_MARKER


def _encode_key(key):
    """Encode AES key before encryption"""
    return key.as_bytes() + KEY_MARKER


def _decode_decryption(d):
    """Check if a decryption is valid and convert it to the right output
    format.

    :param d: decrypted text
    :type d: bytes
    :rtype: int (0/1), AES_key or None if the decryption is invalid
    """
    if d[16:] == INT_MARKER:
        return Crypto.Util.number.bytes_to_long(d[:16])
    elif d[16:] == KEY_MARKER:
        return AES_key.from_bytes(d[:16])
    else:
        # @students: When is this branch taken ?
        # ANSWER: when decrypting a bad line from the GCT (no marker will be
        #          present in the decrypted value)
        return None

