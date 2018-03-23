
# Upload Validation Service AWS Batch ECS Worker AMI

## The AMI

The default ECS Optimized AMIs used for AWS Batch jobs have relatively small filesystems.
As we need to download data files to the instances booted for these batch jobs, we need a larger filesystem.
To achieve this we create a new AMI that:

 - Is based on Amazon's ECS Optimized AMI for our region.
 - Has an additional 1TB filesystem mounted at /data, which we will use for staging files to be validated.

## To create the AMI

### Process Overview

1.  Find latest ECS optimized AMI for your region.
2.  Boot an instance using it.
3.  Create another EBS volume using it's root filesystem snapshot then attach and mount it.
4.  Insert a script into that volume that will format/mount the 1TB volume we will attach.
5.  Unmount and snapshot that volume.
6.  Create a new AMI using the snapshot as the rootfs, that additionally attaches a blank 1TB volume.

### Details

1.  Find the ID of the latest ECS optimized AMI for your region (hereafter: ecosami)
    Try looking here: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs-optimized_AMI.html
2.  Find the ID of the snapshot used to initialize the ecosami's root filesystem:
    AWS Console -> EC2 -> AMIs -> Public Images -> Search -> _ecosami_ -> Details -> Block Devices -> /dev/xvda
    -> snap-xxxxxxxxxxxxxxxxx (hereafter: ecosami-rootfs-snap).
3.  Boot an instance
    1. Use the instance family (e.g. m4) you wish to use for your batch workers
       (as block device mappings can differ between instance type generations).
    1. Use the ecosami AMI
4. AFTER the instance has booted attach another volume.  It is important to do this after boot, as otherwise the
       instance gets confused about which of the two suitable disks it has is the root filesystem.  This way it
       will definitely have the highest minor number.
    1. Create another EBS volume from the ecosami-rootfs-snap
    1. Attach it to the instance you booted.
5.  Login to the system
6.  Mount the new volume on `/mnt`.
    * Run `lsblk` to find your device.
    * In am m4 instance it was `mount /dev/xvdg1 /mnt`
    * In am m5 instance it was `mount /dev/nvme2n1p1 /mnt`
7.  Copy the `dcpfs` init script to `/mnt/etc/init.d`
    1.  Edit the script the fix the BLOCK_DEVICE
      * In an m4 instance it was `/dev/xvdb`
      * In an m5 instance it was `/dev/nvme1n1`
    1.    make symlinks to the appropriate `rc?.d` folders with `chkconfig`
          (note that I tried doing this with `chroot` without success):
```bash
sudo -s
cp /mnt/etc/init.d/dcpfs /etc/init.d
chkconfig --add dcpfs
cd /etc/rc.d
find . -name *dcpfs -type l | xargs tar cf - | (cd /mnt/etc/rc.d ; sudo tar xvf -)
umount /mnt
```
10. Stop the instance
11. Create a snapshot of you new volume
12. Register a new AMI:
    1. Use the new snapshot as the root filesystem
    1. Use the same block device map as the ecosami, with an additional 1 TB /dev/sdb volume

Something like: `aws ec2 register-image --cli-input-json file://register-image.json` with:

```json
{
  "Architecture": "x86_64",
  "BlockDeviceMappings": [
    {
      "DeviceName": "/dev/xvda",
      "Ebs": {
        "DeleteOnTermination": true,
        "SnapshotId": "<your snapshot ID>",
        "VolumeSize": 8,
        "VolumeType": "gp2"
      }
    },
    {
      "DeviceName": "/dev/xvdb",
      "Ebs": {
        "Encrypted": false,
        "DeleteOnTermination": true,
        "VolumeSize": 1096,
        "VolumeType": "gp2"
      }
    },
    {
      "DeviceName": "/dev/xvdcz",
      "Ebs": {
        "Encrypted": false,
        "DeleteOnTermination": true,
        "VolumeSize": 22,
        "VolumeType": "gp2"
      }
    }
  ],
  "Description": "amzn-ami-2017.09.c-amazon-ecs-optimized + 1TB sdb=/data",
  "DryRun": false,
  "EnaSupport": true,
  "Name": "ecso-with-data-vol-v2",
  "RootDeviceName": "/dev/xvda",
  "SriovNetSupport": "simple",
  "VirtualizationType": "hvm"
}
```
