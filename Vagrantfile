# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure(2) do |config|
  
  config.vm.box = "palkosoftware/centos7_x86_64_django_stack"
  config.vm.network "forwarded_port", guest: 8000, host: 9000
  config.vm.network "forwarded_port", guest: 80, host: 9001

  config.ssh.pty = true
  
  #config.ssh.insert_key = true

  config.vm.provider "virtualbox" do |vb|
    vb.memory = "1024"
  end

  config.vm.provision :chef_solo do |chef|
  	chef.version = "12.5.1"
  	chef.log_level = "warn"
  	chef.cookbooks_path = "./cookbooks"
  	chef.add_recipe "projector"

  	chef.json.merge!({
  		:projector => {
  			:server => "nginx",
  			:database => "mariadb",
  			:framework => "django"
  		}
  	})
  end
  
end
