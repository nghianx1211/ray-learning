#!/bin/bash
# restart_ray.sh - Script để restart Ray với resource allocation tối ưu

echo "🛑 Stopping Ray Serve..."
serve shutdown -y 2>/dev/null || true

echo "🛑 Stopping Ray cluster..."
ray stop

echo "⏳ Waiting for Ray to fully stop..."
sleep 3

echo "🚀 Starting Ray with optimized resources..."
# Giảm số CPU reserved cho Ray system để có thêm CPU cho deployments
ray start --head \
    --num-cpus=4 \
    --num-gpus=1 \
    --object-store-memory=4000000000 \
    --dashboard-host=0.0.0.0 \
    --port=6379

echo "✅ Ray started successfully!"
echo ""
echo "📊 Cluster status:"
ray status

echo ""
echo "💡 Bây giờ bạn có thể deploy với:"
echo "   python3 app_v5.py single_model_optimized.yaml"
echo "   hoặc"
echo "   python3 app_v5.py multi_model_config.yaml"
