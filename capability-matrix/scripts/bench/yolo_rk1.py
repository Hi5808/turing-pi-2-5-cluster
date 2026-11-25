import time,statistics as st,json,sys
import numpy as np
from rknnlite.api import RKNNLite
M='/mnt/nvme/npu-bench/vision/vision/yolo/yolov5s_relu_rk3588.rknn'
res={}
for name,mask in (('core0',RKNNLite.NPU_CORE_0),('core0_1_2',RKNNLite.NPU_CORE_0_1_2)):
    r=RKNNLite(); assert r.load_rknn(M)==0
    assert r.init_runtime(core_mask=mask)==0, name
    x=np.random.randint(0,255,(1,640,640,3),dtype=np.uint8)
    for _ in range(20): r.inference(inputs=[x])
    t=[]
    for _ in range(300):
        a=time.perf_counter(); r.inference(inputs=[x]); t.append((time.perf_counter()-a)*1000)
    res[name]={'mean_ms':round(st.mean(t),2),'p50_ms':round(st.median(t),2),'p99_ms':round(sorted(t)[int(.99*len(t))],2),'fps':round(1000/st.mean(t),1)}
    r.release()
print(json.dumps(res,indent=1))
