
# Upload Validation Service AWS Batch ECS Worker AMI

## The AMI

The default ECS Optimized AMIs used for AWS Batch jobs have relatively small filesystems.
As we need to download data files to the instances booted for these batch jobs, we need a larger filesystem.
To achieve this we create a new AMI that:

 - Is based on Amazon's ECS Optimized AMI for our region.
 - Has a modifed block device mapping that causes an additional 1TB volume to be attached
 - Has an init script that formats and mounts the extra volume at /data.

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
    1. Create another EBS volume from the ecosami-rootfs-snap:
       AWS Console -> EC2 -> Elastic Block Store -> Create Volume -> 8GB, _ecosami-rootfs-snap_
    1. Attach it to the instance you booted:
       _volume_ -> _right click_ -> Attach Volume -> _your instance_ -> /dev/sdf
5.  Copy the `dcpfs` scrip to the booted instance:
    `cd amis ; scp dcpfs ec2-user@ec2-X-X-X-X.compute.amazonaws.com:/tmp`
6.  Login to the system (typically as `ec2-user`)
7.  Mount the new volume on `/mnt`:
    * Run `lsblk` to find your device.
    * In an m4 instance it was `sudo mount /dev/xvdg1 /mnt`
    * In an m5 instance it was `sudo mount /dev/nvme1n1p1 /mnt`
8.  Copy the `dcpfs` init script to `/mnt/etc/init.d`
    * Edit the script the fix the BLOCK_DEVICE
    * In an m4 instance it was `/dev/xvdb`
    * In an m5 instance it was `/dev/nvme1n1`
9.  Make symlinks to the appropriate `rc?.d` folders with `chkconfig`
    (note that I tried doing this with `chroot` without success):
```bash
sudo -s
cp /mnt/etc/init.d/dcpfs /etc/init.d
chkconfig --add dcpfs
cd /etc/rc.d
find . -name *dcpfs -type l | xargs tar cf - | (cd /mnt/etc/rc.d ; sudo tar xvf -)
umount /mnt
```
10. Terminate the instance
11. Create a snapshot of you new volume:
    Elastic Block Store -> Volumes -> _volume_ -> _right click_ -> Create Snapshot
12. Craft a JSON register-image decription for your new AMI
    * Start with the output of `aws ec2 register-image --generate-cli-skeleton`
    * Copy as many values as possible from the old AMI.  You can get that info using:
    `aws ec2 describe-images --image-ids ecosapi`
    * Use the new snapshot you created for the root filesystem.
    * Edit the json and add a new stanza to the block device mapping for a 1TB volume.
      Use the next block device number, e.g. if the root fs is `/dev/xvda`, you would use `/dev/xvdb`.
      You should end up with something like:
```json
{
    "Architecture": "x86_64",
    "BlockDeviceMappings": [
        {
            "DeviceName": "/dev/xvda",
            "Ebs": {
                "DeleteOnTermination": true,
                "SnapshotId": "snap-xxxxxxxxxxxxxxxxx",
                "VolumeSize": 30,
                "VolumeType": "gp2"
            }
        },
        {
            "DeviceName": "/dev/xvdb",
            "Ebs": {
                "DeleteOnTermination": true,
                "VolumeSize": 1096,
                "VolumeType": "gp2",
                "Encrypted": false
            }
        }
    ],
    "Description": "Amazon Linux AMI 2.0.20190301 x86_64 ECS HVM GP2 + 1TB@/data",
    "DryRun": false,
    "EnaSupport": true,
    "Name": "ecos-with-data-vol-m5-v2",
    "RootDeviceName": "/dev/xvda",
    "SriovNetSupport": "simple",
    "VirtualizationType": "hvm"
}
```

13. Register the new AMI

    Something like: `aws ec2 register-image --cli-input-json file://register-image.json`

    This AMI will be used in multiple accounts dev+ and prod, so it must
    be made public, so the prod account can access it.  Do that at AWS Console
    -> EC2 -> AMIs -> Owned by me -> _select the AMI_ -> Permissions -> Edit.

14. Cleanup
    * Delete the rootfs EBS volume, you no longer need it.
    * Don't delete the shapshot.  The AMI needs that.

15. See if Batch will use your new AMI.
