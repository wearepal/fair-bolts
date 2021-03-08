"""CelebA DataModule."""
import os
from typing import Optional

import ethicml as em
import ethicml.vision as emvi
from ethicml import implements
from pytorch_lightning import LightningDataModule
from torch.utils.data import DataLoader, Dataset
from torch.utils.data.dataset import T_co, random_split
from torchvision import transforms as TF

from fair_bolts.datasets.ethicml_datasets import Batch


class TiWrapper(Dataset):
    """Wrapper for a Torch Image Datasets."""

    def __init__(self, ti: emvi.TorchImageDataset):
        self.ti = ti

    def __getitem__(self, index) -> T_co:
        x, s, y = self.ti[index]
        return Batch(x=x, s=s, y=y)

    def __len__(self):
        return len(self.ti)


class BaseDm(LightningDataModule):
    """Base DataModule for this project."""

    def __init__(self, data_dir, batch_size, workers, val_pcnt, shrink_pcnt, y_dim, s_dim):
        super().__init__()
        self.data_dir = data_dir if data_dir is not None else os.getcwd()
        self.batch_size = batch_size
        self.num_workers = workers
        self.val_pcnt = val_pcnt
        self.shrink_pcnt = shrink_pcnt
        self.y_dim = y_dim
        self.s_dim = s_dim

        self.train_data: Optional[Dataset] = None
        self.test_data: Optional[Dataset] = None
        self.val_data: Optional[Dataset] = None


class CelebaDataModule(BaseDm):
    """CelebA Dataset."""

    def __init__(
        self,
        data_dir: Optional[str] = None,
        batch_size: int = 32,
        num_workers: int = 0,
        shrink_pcnt: float = 1.0,
        val_split: float = 0.2,
    ):
        super().__init__(data_dir, batch_size, num_workers, val_split, shrink_pcnt, 1, 1)
        self.dims = (3, 64, 64)

    @implements(LightningDataModule)
    def prepare_data(self, *args, **kwargs):
        _, _ = em.celeba(
            download_dir=self.data_dir,
            label="Smiling",
            sens_attr="Male",
            download=True,
            check_integrity=True,
        )

    @implements(LightningDataModule)
    def setup(self, stage: Optional[str] = None) -> None:
        dataset, base_dir = em.celeba(
            download_dir=self.data_dir,
            label="Smiling",
            sens_attr="Male",
            download=False,
            check_integrity=True,
        )

        tform_ls = [TF.Resize(64), TF.CenterCrop(64)]
        tform_ls.append(TF.ToTensor())
        tform_ls.append(TF.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)))
        transform = TF.Compose(tform_ls)

        assert dataset is not None
        all_data = TiWrapper(
            emvi.TorchImageDataset(
                data=dataset.load(), root=base_dir, transform=transform, target_transform=None
            )
        )

        data_len = int(len(all_data) * self.shrink_pcnt)

        test_len = int(data_len * 0.2)
        train_len = data_len - test_len
        val_len = int(self.val_pcnt * train_len)
        train_len -= val_len

        train_data, val_data, test_data, _ = random_split(
            all_data,
            lengths=(train_len, val_len, test_len, len(all_data) - train_len - val_len - test_len),
        )

        self.train_data = train_data
        self.val_data = val_data
        self.test_data = test_data

    def make_dataloader(self, ds, shuffle=False):
        """Make DataLoader."""
        return DataLoader(
            ds,
            batch_size=self.batch_size,
            shuffle=shuffle,
            num_workers=self.num_workers,
            pin_memory=True,
        )

    @implements(LightningDataModule)
    def train_dataloader(self, shuffle: bool = False, drop_last: bool = False) -> DataLoader:
        return self.make_dataloader(self.train_data, shuffle=True)

    @implements(LightningDataModule)
    def val_dataloader(self, shuffle: bool = False, drop_last: bool = False) -> DataLoader:
        return self.make_dataloader(self.val_data)

    @implements(LightningDataModule)
    def test_dataloader(self, shuffle: bool = False, drop_last: bool = False) -> DataLoader:
        return self.make_dataloader(self.test_data)
