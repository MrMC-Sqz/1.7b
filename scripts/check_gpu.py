import torch


def main() -> None:
    print("cuda_available=", torch.cuda.is_available())
    print("cuda_count=", torch.cuda.device_count())
    if torch.cuda.is_available():
        for i in range(torch.cuda.device_count()):
            print(f"cuda[{i}]=", torch.cuda.get_device_name(i))


if __name__ == "__main__":
    main()
