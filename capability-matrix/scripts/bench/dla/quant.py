#!/usr/bin/env python3
"""Make an INT8 QDQ resnet18 for DLA.

Calibration uses RANDOM tensors, not real images. That is sufficient to place
QDQ nodes and measure THROUGHPUT, and it makes the model's ACCURACY MEANINGLESS.
Nothing about accuracy may be claimed from an engine built this way.
"""
import sys
import numpy as np
import onnx
from onnx import version_converter
from onnxruntime.quantization import quantize_static, CalibrationDataReader, QuantType, QuantFormat

SRC, DST = "resnet18_fp16.onnx", "resnet18_int8.onnx"

# DLA wants fp32 I/O for the QDQ path; the source is fp16, so cast it first.
m = onnx.load(SRC)
try:
    from onnxconverter_common import float16
    print("have float16 helper")
except Exception:
    pass

# Find input name/shape
inp = m.graph.input[0]
name = inp.name
shape = [(d.dim_value if d.dim_value > 0 else 1) for d in inp.type.tensor_type.shape.dim]
print("input", name, shape, "elem_type", inp.type.tensor_type.elem_type)


class R(CalibrationDataReader):
    def __init__(self, n=32):
        dt = np.float16 if inp.type.tensor_type.elem_type == onnx.TensorProto.FLOAT16 else np.float32
        self.data = [{name: np.random.rand(*shape).astype(dt)} for _ in range(n)]
        self.i = iter(self.data)
    def get_next(self):
        return next(self.i, None)


quantize_static(SRC, DST, R(), quant_format=QuantFormat.QDQ,
                activation_type=QuantType.QInt8, weight_type=QuantType.QInt8,
                per_channel=False, reduce_range=False,
                extra_options={"ActivationSymmetric": True, "WeightSymmetric": True, "QuantizeBias": False})
print("wrote", DST)
q = onnx.load(DST)
ops = {}
for n_ in q.graph.node:
    ops[n_.op_type] = ops.get(n_.op_type, 0) + 1
print("op counts:", {k: v for k, v in sorted(ops.items()) if k in ("QuantizeLinear", "DequantizeLinear", "Conv", "QLinearConv")})
