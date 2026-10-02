# Round17 controlled training commands

Working directory: `@project`.

All runs use the same V base checkpoint, the same validation split, 640 px, batch 8, 100 epochs, and seed 0. The four cells differ only in the training-label variant and optimizer policy. The existing Round16 reviewed-label AdamW cell is reused rather than retrained.

## Original labels + explicit AdamW

```bash
WANDB_MODE=disabled WANDB_DISABLED=true COMET_DISABLE_AUTO_LOGGING=1 @server_home/bin/python code/tools/dji_train_explicit_adamw.py --weights results/dji_adaptation/b4_trial_v7/runs_round14_960/V_960_recovery5/weights/best.pt --data results/dji_adaptation/b4_trial_v7/datasets_round12_copy_abs/V/data.yaml --project results/dji_adaptation/b4_trial_v7/runs_round17_control --name V_base_labels_adamw_wandboff --epochs 100 --imgsz 640 --batch 8 --lr0 0.0005 --device 0 --workers 2 --seed 0
```

## Reviewed labels + auto optimizer

```bash
WANDB_MODE=disabled WANDB_DISABLED=true COMET_DISABLE_AUTO_LOGGING=1 @server_home/bin/python code/tools/dji_train_optimizer_control_v2.py --weights results/dji_adaptation/b4_trial_v7/runs_round14_960/V_960_recovery5/weights/best.pt --data results/dji_adaptation/b4_trial_v7/datasets_round16_reviewed_v/V/data.yaml --project results/dji_adaptation/b4_trial_v7/runs_round17_control --name V_reviewed_labels_auto_wandboff --epochs 100 --imgsz 640 --batch 8 --lr0 0.0005 --optimizer auto --device 1 --workers 2 --seed 0
```

On this server, logical `CUDA:1` mapped to physical GPU 0. This was checked with `nvidia-smi --query-compute-apps` and does not alter the model/data comparison.

## Original labels + auto optimizer

```bash
CUDA_VISIBLE_DEVICES=1 WANDB_MODE=disabled WANDB_DISABLED=true COMET_DISABLE_AUTO_LOGGING=1 @server_home/bin/python code/tools/dji_train_optimizer_control_v2.py --weights results/dji_adaptation/b4_trial_v7/runs_round14_960/V_960_recovery5/weights/best.pt --data results/dji_adaptation/b4_trial_v7/datasets_round12_copy_abs/V/data.yaml --project results/dji_adaptation/b4_trial_v7/runs_round17_control --name V_base_labels_auto_visible_gpu1 --epochs 100 --imgsz 640 --batch 8 --lr0 0.0005 --optimizer auto --device 0 --workers 2 --seed 0
```

With `CUDA_VISIBLE_DEVICES=1`, logical `CUDA:0` mapped to physical GPU 1. Auto optimizer may override the requested learning rate; inspect each run's `args.yaml` for the effective setting. Blind-test data is not read.
