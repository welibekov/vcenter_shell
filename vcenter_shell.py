#!/usr/bin/env python
#

from cmd import Cmd
from core import *
import os

class VcenterShell(Cmd):
    def __init__(self):
        Cmd.__init__(self)
        self.intro =  '####\n#### Welcome to vcenter shell. Type help or ? to list commands. ####\n####\n'
        self.doc_header = 'To find info and example fo particular command please type \'help command\''
        self.prompt = '[vc001]$ '

    def default(self, line):
        print("{}: Command not found".format(line))

    def do_exit(self, line):
        '''exit the shell.'''
        print("Exiting...")
        return True
   
    def do_clear(self, line):
        '''clear screen'''
        os.system('clear')

    def do_connect_to_api(self, line):
        '''connect to vcenter api service'''
        print("Connecting to vcenter...")
        self.content = connect_to_api().RetrieveContent()
        print("Connected")

    def do_list_clusters(self, line):
        '''list configured clusters'''
        HEADER = ['NAME','CPU','THREADS','MEMORY','HOSTS','STATUS']
        HBODY = "{0:<10s} {1:<10s} {2:<10s} {3:<10s} {4:<10s} {5:<10s}"
        BODY = "{0:<10s} {1:<10d} {2:<10d} {3:<10.0f} {4:<10d} {5:<10s}"
        clusters = list_clusters(self.content)
        clusters.update({HEADER[0]:HEADER[1:]})
        for cluster,info in sorted(clusters.items(),reverse=True):
            if cluster == 'NAME':
                print(HBODY.format(cluster,*info))
                print("-"*len(HEADER[0]))
            else:
                print(BODY.format(cluster,*info))

    def do_list_datastores(self, line):
        '''list configured datastores'''
        HEADER = ['NAME','CAPACITY','FREE','STATUS']
        HBODY = "{0:<25s} {1:<15s} {2:<15s} {3:<15s}"
        BODY = "{0:<25s} {1:<15.0f} {2:<15.0f} {3:<15s}"
        datastores = list_datastores(self.content)
        datastores.update({HEADER[0]:HEADER[1:]})
        for datastore,info in sorted(datastores.items(),reverse=True):
            if datastore == 'NAME':
                print(HBODY.format(datastore,*info))
                print("-"*len(''.join(HEADER[0])))
            else:
                print(BODY.format(datastore,*info))
        
    def do_list_tenants(self, line):
        '''list existing tenants'''
        HEADER = ['NAME']
        HBODY = "{0:<10s}"
        tenants = list_tenants(self.content)
        tenants.append(HEADER[0])
        tenants.reverse()
        for index,tenant in enumerate(tenants):
            if tenant == 'NAME':
                print(HBODY.format(tenant))
                print("-"*len(''.join(HEADER[0])))
            else:
                print("[{}] {}".format(index,tenant))
    
    def do_list_vms(self, line):
        '''
        list vms in tenant
        Example: list_vms TENANT_NAME 
        '''
        try:
            args = line.split()
            vms = list_vms(self.content,args[0])
            for vm,info in sorted(vms.items()):
                if info[0] == 'v' or info[0] == 't':
                    #print("{0} -- {1:<20} {2:>5} {3:>5} {4:>5} {5:>5}".format(info[0],vm,*info[1:]))
                    #print("{} -- {} {} {} {} {} {} {}".format(info[0],vm,*info[1:]))
                    print(info[0],vm,*info[1:])
                elif info[0] == 'd':
                    print("{0} -- {1}".format(info[0],vm))
        except AttributeError:
            print("Not found")
        except IndexError:
            pass
   
    def do_list_templates(self, line):
        '''
        list available templates in Templates\linux
        '''
        folder = get_templates_folder(self.content)
        templates = list_templates(folder,{})
        for name,guest in sorted(templates.items()):
            print("t -- {}  ['{}']".format(name,guest))
       
    def do_find_vm(self,line):
        '''
        find virtual machine by name
        Example: find_vm NAME
        '''
        args = line.split()
        vm = find_vm(self.content,args[0])
        if vm:
            for key,val in vm.items():
                print("{} -- {} {} {} {} {} {} {} {}".format(key,*val))
        else:
            print('No vm with {} name found'.format(args[0]))

    def do_list_dvs(self,line):
        '''
        list available DVS
        '''
        dvs = list_dvs(self.content)
        for i,switch in enumerate(dvs,1):
            print("[{}] {}".format(i,switch))

    def do_dvs_info(self, line):
        '''
        Get DVS info
        Example: dvs_info DVS_NAME
        '''
        args = line.split()
        dvs = dvs_info(self.content,name=args[0])
        print(dvs)
           
    def do_clone(self, line):
        '''
        Clone virtual machine from template
        Example: clone NAME TEMPLATE TENANT CLUSTER DATASTORE CPU RAM HDD EPG
        '''
        args = line.split()
        try:
            vm_name,template,tenant,cluster,datestore,cpu,ram,hdd,epg = args
        except ValueError:
            print('Please provide arguments as in help')
        try:
            print("Cloning {} to {}...".format(template,vm_name))
            clone(self.content,vm_name,template,tenant,cluster,datestore)
            print("Completed")
        except Exception:
            print("Could not clone {} :-(".format(vm_name))
        try:
            print("Changing {} settings...".format(vm_name))
            vm_settings(self.content,vm_name,cpu,ram,hdd,epg)
            print("Completed")
        except Exception:
            print("Could not change settings to {} :-(".format(vm_name))

    def do_clone_from_file(self, line):
        '''
        Clone virtual machine from template but take config from the file
        Examples: clone_from_file FILENAME
        FILENAME syntax ini style. Please check examples
        '''
        pass

    def do_start_vm(self, line):
        '''
        Start virtual machine
        Examples: start_vm NAME
        '''
        args = line.split()
        vm = get_obj(self.content,[vim.VirtualMachine],name=args[0])
        if vm:
            print("Poweron {}...".format(vm.name))
            task = vm.PowerOnVM_Task()
            wait_for_task(task)
            print("Started!")
        else:
            print("No vm with {} name found".format(args[0]))

    def do_stop_vm(self, line):
        '''
        Stop virtual machine
        Examples: stop_vm NAME
        '''
        args = line.split()
        vm = get_obj(self.content,[vim.VirtualMachine],name=args[0])
        if vm:
            print("Poweroff {}...".format(vm.name))
            task = vm.PowerOffVM_Task()
            wait_for_task(task)
            print("Stopped!")
        else:
            print("No vm with {} name found".format(args[0]))

    def do_reset_vm(self, line):
        '''
        Reset virtual machine
        Examples: reset_vm NAME
        '''
        args = line.split()
        vm = get_obj(self.content,[vim.VirtualMachine],name=args[0])
        if vm:
            print("Reseting {}...".format(vm.name))
            task = vm.ResetVM_Task()
            wait_for_task(task)
            print("Done!")
        else:
            print("No vm with {} name found".format(args[0]))

    def do_remove_vm(self, line):
        '''
        Remove virtual machine
        Examples: remove_vm NAME
        '''
        args = line.split()
        try:
            vm = get_obj(self.content,[vim.VirtualMachine],name=args[0])
            if vm:
                if vm.runtime.powerState == "poweredOn":
                    print("Attempting to poweroff {}".format(args[0]))
                    task = vm.PowerOffVM_Task()
                    wait_for_task(task)
                print("Destroying {}...".format(args[0]))
                task = vm.Destroy_Task()
                wait_for_task(task)
                print("Done!")
        except Exception:
            pass
 
    def do_vm_info(self, line):
        '''
        View virtual machine config/hardware settings
        Example: vm_info NAME
        '''
        args = line.split()
        vm = get_obj(self.content,[vim.VirtualMachine],name=args[0])
        config_info = vm_info(vm)
        print('NAME\n----')
        for info in config_info:
            print("{}\t".format(info),end='')
        print()

if __name__ == '__main__':
    myshell = VcenterShell()
    try:
        myshell.cmdloop()
    except KeyboardInterrupt:
        print("Exiting...")
        
    