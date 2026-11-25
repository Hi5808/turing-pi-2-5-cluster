#!/usr/bin/env python3
"""Two models identical except for one op, to isolate GPU fallback as the ceiling's cause.

  conv_pure     : Conv -> Relu, x8. Every op is DLA-native, so a strict-DLA engine
                  (no --allowGPUFallback) must compile and the GPU is never touched.
  conv_fallback : the same chain plus ONE residual Add, which DLA rejects
                  ("ElementWise SUM requires non-empty inputs"), forcing a DLA->GPU->DLA
                  round trip per inference and nothing else.

Weights are tiny (590 KB) and arithmetic is high, so neither model is bandwidth-bound.
If the ~253 qps ceiling is fallback sync, conv_pure scales across the two engines and
conv_fallback does not. If both stall, the ceiling is something else.
"""
import numpy as np, onnx
from onnx import helper, TensorProto, numpy_helper

C, HW, NCONV = 64, 56, 8
rng = np.random.default_rng(0)


def build(path, add_residual):
    nodes, inits = [], []
    cur = "input"
    for i in range(NCONV):
        w = rng.standard_normal((C, C, 3, 3)).astype(np.float16) * 0.02
        inits.append(numpy_helper.from_array(w, f"w{i}"))
        nodes.append(helper.make_node("Conv", [cur, f"w{i}"], [f"c{i}"],
                                      kernel_shape=[3, 3], pads=[1, 1, 1, 1], name=f"conv{i}"))
        nodes.append(helper.make_node("Relu", [f"c{i}"], [f"r{i}"], name=f"relu{i}"))
        cur = f"r{i}"
    if add_residual:
        # The ONE difference: a residual add DLA will not take.
        nodes.append(helper.make_node("Add", ["r0", cur], ["out_add"], name="residual"))
        cur = "out_add"
    g = helper.make_graph(
        nodes, "m",
        [helper.make_tensor_value_info("input", TensorProto.FLOAT16, [1, C, HW, HW])],
        [helper.make_tensor_value_info(cur, TensorProto.FLOAT16, [1, C, HW, HW])],
        inits)
    m = helper.make_model(g, opset_imports=[helper.make_opsetid("", 13)])
    m.ir_version = 9
    onnx.checker.check_model(m)
    onnx.save(m, path)
    wb = sum(int(np.prod(numpy_helper.to_array(i).shape)) for i in inits) * 2
    act = C * HW * HW * 2
    print(f"{path}: {NCONV} conv, weights {wb/1e6:.3f} MB, activation {act/1e6:.3f} MB, "
          f"residual_add={add_residual}")


build("conv_pure.onnx", False)
build("conv_fallback.onnx", True)
