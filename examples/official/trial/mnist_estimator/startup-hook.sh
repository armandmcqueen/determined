#export TF_CONFIG='{"cluster": {"worker": ["localhost:12345", "localhost:12346", "localhost:12347"], "chief": ["localhost:12349"]}, "task": {"type": "worker", "index": 1}}'

#python -c "import tensorflow_estimator; print(tensorflow_estimator.__file__)"

cp -pv /run/determined/workdir/hotpatches/determined/_estimator_trial_hotpatch.py /run/determined/pythonuserbase/lib/python3.6/site-packages/determined/estimator/_estimator_trial.py
cp -pv /run/determined/workdir/hotpatches/estimator/dnn_hotpatch.py /opt/conda/lib/python3.6/site-packages/tensorflow_estimator/python/estimator/canned/dnn.py
cp -pv /run/determined/workdir/hotpatches/estimator/training_hotpatch.py /opt/conda/lib/python3.6/site-packages/tensorflow_estimator/python/estimator/training.py
cp -pv /run/determined/workdir/hotpatches/estimator/run_config_hotpatch.py /opt/conda/lib/python3.6/site-packages/tensorflow_estimator/python/estimator/run_config.py
cp -pv /run/determined/workdir/hotpatches/estimator/estimator_hotpatch.py /opt/conda/lib/python3.6/site-packages/tensorflow_estimator/python/estimator/estimator.py

cp -pv /run/determined/workdir/hotpatches/tensorflow/ops_hotpatch.py /opt/conda/lib/python3.6/site-packages/tensorflow_core/python/framework/ops.py
cp -pv /run/determined/workdir/hotpatches/tensorflow/device_spec_hotpatch.py /opt/conda/lib/python3.6/site-packages/tensorflow_core/python/framework/device_spec.py
cp -pv /run/determined/workdir/hotpatches/tensorflow/config_hotpatch.py /opt/conda/lib/python3.6/site-packages/tensorflow_core/python/framework/config.py
cp -pv /run/determined/workdir/hotpatches/tensorflow/framework_device_hotpatch.py /opt/conda/lib/python3.6/site-packages/tensorflow_core/python/framework/device.py

cp -pv /run/determined/workdir/hotpatches/tensorflow/device_lib_hotpatch.py /opt/conda/lib/python3.6/site-packages/tensorflow_core/python/client/device_lib.py
cp -pv /run/determined/workdir/hotpatches/tensorflow/session_hotpatch.py /opt/conda/lib/python3.6/site-packages/tensorflow_core/python/client/session.py