# Guide how to run with fake llm

## Requirement
- Access to gke cluster
- Have enough resource (2-3 node for e2-standard-4)
- Have artifact repository


## 1. Build and push image to artifact repository
```bash
docker build -t asia-southeast1-docker.pkg.dev/kubernetes-468114/test/fake-llm-ray:latest .

docker push asia-southeast1-docker.pkg.dev/kubernetes-468114/test/fake-llm-ray:latest
```

## 2. Install kuberay operator
```bash
helm repo add kuberay https://ray-project.github.io/kuberay-helm/
helm repo update
helm install kuberay-operator kuberay/kuberay-operator   --namespace ray   --version 1.4.2
```

## 3. Run ray service
```bash
kubectl apply -f rayservice-fake-llm.yaml
```

## 4. Result after run
```bash
service will have 2 svc
- service of head node with no suffix (for other call generic)
- service of head node with suffix (for manage and scale)

pods will have 2 pods
- pod of head node with (2 container) side-car container for autoscale and 1 for chạy thực tế
- pod of worker node
```

> Nếu ko đủ thì tức là đã có config sai


## 5. Expose port for service and dashboard
```bash
kubectl port-forward svc/fake-llm-service-head-svc 8000:8000 8265:8265

# Can view information by open localhost:8265
```

## 6. load test for check autoscale
```bash
chmod +x load_test.sh
./load_test.sh 
```