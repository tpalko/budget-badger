# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure(2) do |config|
  
  config.vm.box = "CentOS6.6_Nginx_Postgres_Django"
  config.vm.network "forwarded_port", guest: 80, host: 9001

  #config.ssh.insert_key = true

  config.vm.provider "virtualbox" do |vb|
    vb.memory = "1024"
  end
  
end
