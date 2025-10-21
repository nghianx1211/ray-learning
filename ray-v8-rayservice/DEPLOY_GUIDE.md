# 🚀 Quick Deployment Guide - Ray VLLM Service

## Prerequisites
- ✅ Docker image đã build xong
- ✅ Kubernetes cluster với GPU nodes
- ✅ KubeRay Operator đã cài đặt
- ✅ kubectl configured

---

## Step 1: Push Docker Image

```powershell
# Set your registry info
$PROJECT_ID = "kubernetes-468114"
$REGION = "asia-southeast1"
$REPOSITORY = "test"
$IMAGE_NAME = "ray-vllm-serve"
$VERSION = "v8-latest"

# Configure Docker
gcloud auth configure-docker ${REGION}-docker.pkg.dev

# Tag image
docker tag ray-vllm-service:v2.49.0 `
  ${REGION}-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/${IMAGE_NAME}:$VERSION

# Push image
docker push ${REGION}-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/${IMAGE_NAME}:$VERSION
```

---

## Step 2: Install KubeRay Operator (nếu chưa có)

```powershell
# Add Helm repo
helm repo add kuberay https://ray-project.github.io/kuberay-helm/
helm repo update

# Install operator
helm install kuberay-operator kuberay/kuberay-operator `
  --namespace ray-system `
  --create-namespace `
  --version 1.2.2

# Verify
kubectl get pods -n ray-system
```

---

## Step 3: Update Image Path trong rayservice.yaml

Mở file `rayservice.yaml` và tìm 2 dòng:
```yaml
# Line ~150 và ~270
image: asia-southeast1-docker.pkg.dev/kubernetes-468114/test/ray-vllm-serve:v8-latest
```

Thay bằng image path thực tế của bạn.

---

## Step 4: Deploy RayService

```powershell
# Apply toàn bộ
kubectl apply -f rayservice.yaml

# Hoặc apply từng phần
kubectl apply -f rayservice.yaml -n default

# Output:
# configmap/ray-model-config created
# persistentvolumeclaim/ray-model-storage created
# rayservice.ray.io/multi-model-llm-service created
# service/ray-vllm-serve created
```

---

## Step 5: Monitor Deployment

```powershell
# Watch RayService status
kubectl get rayservice multi-model-llm-service -w

# Watch pods
kubectl get pods -l app=ray-vllm -w

# Expected output:
# NAME                                        READY   STATUS    RESTARTS   AGE
# multi-model-llm-service-raycluster-head-xxx  1/1    Running   0          2m
# multi-model-llm-service-raycluster-worker-xxx 1/1   Running   0          2m
```

### View logs
```powershell
# Head node logs
kubectl logs -f -l component=ray-head

# Worker logs  
kubectl logs -f -l component=ray-worker
```

---

## Step 6: Test API

### Port-forward
```powershell
# Forward Serve port
kubectl port-forward svc/ray-vllm-serve 8000:8000

# Forward Dashboard (trong terminal khác)
kubectl port-forward svc/ray-vllm-serve 8265:8265
```

### Test endpoints
```powershell
# Health check
curl http://localhost:8000/-/healthz

# List models
curl http://localhost:8000/v1/models

# Test inference
$body = @{
    model_id = "falcone-3b-instruct"
    input = "Hello, how are you?"
    params = @{
        max_tokens = 256
        temperature = 0.7
    }
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/v1/infer" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

### Test với Python
```python
import requests

response = requests.post(
    "http://localhost:8000/v1/chat/completions",
    json={
        "model": "falcone-3b-instruct",
        "messages": [
            {"role": "user", "content": "Tell me a joke"}
        ],
        "max_tokens": 256
    }
)
print(response.json())
```

---

## 📊 Monitoring

### Ray Dashboard
```powershell
# Access at http://localhost:8265
kubectl port-forward svc/ray-vllm-serve 8265:8265
```

### Check Resources
```powershell
# Pod resources
kubectl top pods -l app=ray-vllm

# Node resources
kubectl top nodes

# Describe pod
kubectl describe pod -l component=ray-worker
```

### Exec into pod
```powershell
# Get pod name
$POD = kubectl get pods -l component=ray-head -o jsonpath='{.items[0].metadata.name}'

# Exec
kubectl exec -it $POD -- bash

# Inside pod:
ray status
nvidia-smi
ls -lh /mnt/models/.cache
```

---

## 🔧 Common Issues

### Image Pull Error
```powershell
# Create image pull secret
kubectl create secret docker-registry gcr-secret `
  --docker-server=asia-southeast1-docker.pkg.dev `
  --docker-username=_json_key `
  --docker-password="$(Get-Content -Path key.json -Raw)" `
  -n default
```

Add to rayservice.yaml:
```yaml
spec:
  rayClusterConfig:
    headGroupSpec:
      template:
        spec:
          imagePullSecrets:
            - name: gcr-secret
```

### Pod Pending (No GPU)
```powershell
# Check GPU nodes
kubectl get nodes -o json | ConvertFrom-Json | 
  Select-Object -ExpandProperty items | 
  Where-Object { $_.status.capacity.'nvidia.com/gpu' }

# Scale GPU nodes (GKE)
gcloud container clusters resize YOUR_CLUSTER `
  --node-pool=gpu-pool `
  --num-nodes=2
```

### Model Loading Timeout
```yaml
# Increase timeout in rayservice.yaml
livenessProbe:
  initialDelaySeconds: 300  # Increase from 60
```

---

## 🔄 Update và Scale

### Update config
```powershell
# Edit ConfigMap
kubectl edit configmap ray-model-config

# Apply changes
kubectl apply -f rayservice.yaml

# Restart to reload
kubectl delete pod -l app=ray-vllm
```

### Scale workers
```powershell
# Edit rayservice.yaml
# Change: replicas, minReplicas, maxReplicas

# Apply
kubectl apply -f rayservice.yaml
```

---

## 🧹 Cleanup

```powershell
# Delete all resources
kubectl delete -f rayservice.yaml

# Delete namespace
kubectl delete namespace ray-system

# Uninstall operator
helm uninstall kuberay-operator -n ray-system
```

---

## 🎯 Architecture Flow

```
Client Request
    ↓
LoadBalancer Service (ray-vllm-serve:8000)
    ↓
RayService CRD
    ↓
Ray Head Pod (ray-head)
    ├── Ray Serve Controller
    └── Ray Dashboard (8265)
    ↓
Ray Worker Pods (GPU)
    ├── MultiModelDeployment
    ├── MultiModelServer
    └── VLLMEngine (GPU)
```

---

## 📝 Files Structure

```
rayservice.yaml              # Main deployment file
  ├── RayService             # KubeRay CRD
  ├── ConfigMap              # model_config.yaml
  ├── PVC                    # Model storage
  ├── Service                # LoadBalancer
  └── Ingress (optional)     # HTTPS

builders/
  ├── rayservice_wrapper.py  # RayService entry point
  └── app_builder.py         # Application builder

serve/
  ├── deployments/
  │   ├── multi_model_deployment.py
  │   └── multi_model_server.py
  └── router/
      └── router.py

servers/
  └── vllm_engine.py
```

---

## 🎉 That's it!

Your Ray VLLM service is now running on Kubernetes with:
- ✅ Auto-scaling
- ✅ GPU optimization  
- ✅ Multi-model support
- ✅ OpenAI-compatible API
- ✅ Health monitoring

For issues, check logs:
```powershell
kubectl logs -f -l app=ray-vllm --all-containers=true
```
