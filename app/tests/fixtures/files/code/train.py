import yaml
from eval import evaluate


def main(config_path="configs/default.yaml"):
    cfg = yaml.safe_load(open(config_path))
    lr = cfg["learning_rate"]
    print("training with", lr)
    evaluate(cfg)


if __name__ == "__main__":
    main()
