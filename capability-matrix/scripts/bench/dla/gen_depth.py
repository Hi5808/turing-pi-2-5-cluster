#!/usr/bin/env python3
"""conv_dN.onnx: N x (Conv 3x3 64->64 + ReLU), all DLA-native, strict-buildable."""
import numpy as np, onnx
from onnx import helper, TensorProto, numpy_helper

C, HW = 64, 56
rng = np.random.default_rng(0)
for N in (2, 8, 32):
    nodes, inits, cur = [], [], "input"
    for i in range(N):
        w = (rng.standard_normal((C, C, 3, 3)).astype(np.float16)) * 0.02
        inits.append(numpy_helper.from_array(w, f"w{i}"))
        nodes.append(helper.make_node("Conv", [cur, f"w{i}"], [f"c{i}"],
                                      kernel_shape=[3, 3], pads=[1, 1, 1, 1], name=f"conv{i}"))
        nodes.append(helper.make_node("Relu", [f"c{i}"], [f"r{i}"], name=f"relu{i}"))
        cur = f"r{i}"
    g = helper.make_graph(nodes, "m",
        [helper.make_tensor_value_info("input", TensorProto.FLOAT16, [1, C, HW, HW])],
        [helper.make_tensor_value_info(cur, TensorProto.FLOAT16, [1, C, HW, HW])], inits)
    m = helper.make_model(g, opset_imports=[helper.make_opsetid("", 13)])
    m.ir_version = 9
    onnx.checker.check_model(m)
    onnx.save(m, f"conv_d{N}.onnx")
    print(f"conv_d{N}.onnx: {N} conv, weights {N*C*C*9*2/1e6:.3f} MB")
