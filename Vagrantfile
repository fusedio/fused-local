# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure("2") do |config|
    config.vm.box = "ubuntu/jammy64"

    # Create a forwarded port mapping which allows access to a specific port
    # within the machine from a port on the host machine and only allow access
    # via 127.0.0.1 to disable public access
    config.vm.network "forwarded_port", guest: 8000, host: 8000, host_ip: "127.0.0.1"

    # Sync the project files
    # Note this is a one-time, one-way sync from the host to the guest.
    # Otherwise it's hard to keep them from stepping on each other's .venv
    config.vm.synced_folder ".", "/vagrant",
        type: 'rsync',
        rsync__exclude: [
            ".venv/", "node_modules/", "**/__pycache__/", ".git/"
        ]

    config.vm.provider "virtualbox" do |vb|
        # Display the VirtualBox GUI when booting the machine
        # vb.gui = true

        # Customize the resources on the VM:
        vb.memory = "8192"
        vb.cpus = 8
    end


    config.vm.provision "shell", privileged: false, inline: <<-SHELL
        # # Update and upgrade the system
        # sudo apt-get update
        # sudo apt-get upgrade -y

        # Install Rye
        curl -sSf https://rye.astral.sh/get | RYE_INSTALL_OPTION="--yes" bash
        source "$HOME/.rye/env"

        # Run rye sync
        cd /vagrant
        bash -c "rye sync"
    SHELL
end