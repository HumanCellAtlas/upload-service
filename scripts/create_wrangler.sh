#!/bin/bash
# This script creates a user and adds them to the established wrangler group

echo "Type username, followed by [ENTER]:"
read user
adduser $user
adduser $user wranglers
mkdir -p /home/$user/.ssh
touch /home/$user/.ssh/authorized_keys
chmod 700 /home/$user/.ssh
chmod 644 /home/$user/.ssh/authorized_keys
echo "Type user public ssh key, followed by [ENTER]:"
read userkey
echo $userkey >> /home/$user/.ssh/authorized_keys
cd /home/$user
hca
chown -R $user:$user /home/$user/
