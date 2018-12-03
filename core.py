#!/usr/bin/env python3
#
# Core modules for operate with vcenter

from pyVim.connect import SmartConnectNoSSL, Disconnect
from pyVmomi import vim
import json
import atexit

GB = 1024*1024*1024
__credentials__ = '.credentials'

def vc_credentials(filename):
    with open(filename) as f:
        credentials = json.load(f)
    return credentials

def get_obj(content, vimtype, name=None):
    obj = None
    container = content.viewManager.CreateContainerView(
                content.rootFolder, vimtype, True)
    if not name:
        obj = container
        return obj
    for c in container.view:
        if name:
            if c.name == name:
                obj = c
                break
        else:
            obj = c
            break
    return obj

def wait_for_task(task):
    """ wait for vcenter task to complete """
    task_done = False
    while not task_done:
        if task.info.state == 'success':
            return task.info.state

        if task.info.state == 'error':
            print("error occured")
            task_done = True

def connect_to_api(creds=vc_credentials):
    try:
        creds = vc_credentials(__credentials__)
    except FileNotFoundError:
        raise SystemExit('No .credentials file found')
    SI = None
    try:
        SI = SmartConnectNoSSL(host=creds['VC_HOST'],
                               user=creds['VC_USER'],
                               pwd=creds['VC_PASS'],
                               port=creds['VC_PORT'])
        
        atexit.register(Disconnect, SI)
    except IOError as ex:
        pass

    if not SI:
        raise SystemExit("Unable to connect to vcenter.")
    return SI

# ---
# ---

def vm_info(vm):
    return list(map(str,[vm.name, vm.summary.config.numCpu,
            vm.summary.config.memorySizeMB,
            ','.join([str(i.capacityInKB) for i in vm.config.hardware.device if isinstance(i,vim.vm.device.VirtualDisk)]),
            vm.summary.config.vmPathName.split()[0],
            vm.summary.config.guestFullName,
            ','.join([i.macAddress for i in vm.config.hardware.device if hasattr(i,'macAddress')]),
            ','.join([i.name for i in vm.network]),
            vm.summary.runtime.powerState]))

def list_tenants(content,vmtype=[vim.Folder],name="Tenants"):
    tn_obj = get_obj(content,vmtype,name)
    return [tenant.name for tenant in tn_obj.childEntity if not hasattr(tenant,"PowerOff")]
        
def list_clusters(content,vmtype=[vim.ClusterComputeResource]):
    cl_obj = get_obj(content,[vim.ClusterComputeResource])
    cl_view = cl_obj.view
    cl_obj.DestroyView()
    return {cl.name:[cl.summary.numCpuCores,
                     cl.summary.numCpuThreads,
                     float(cl.summary.totalMemory)/GB,
                     cl.summary.numHosts,
                     cl.summary.overallStatus] for cl in cl_view}

def list_datastores(content,vmtype=[vim.Datastore]):
    out = {}
    ds_obj = get_obj(content,[vim.Datastore])
    ds_view = ds_obj.view
    ds_obj.DestroyView()
    out.update({ds.name:[int(ds.summary.capacity)/GB, 
                    int(ds.summary.freeSpace)/GB, 
                    ds.overallStatus,'DS'] for ds in ds_view})
    # storege DRS
    ds_obj = get_obj(content,[vim.StoragePod])
    ds_view = ds_obj.view
    ds_obj.DestroyView()
    out.update({ds.name:[int(ds.summary.capacity)/GB, 
                    int(ds.summary.freeSpace)/GB,
                    ds.overallStatus,'DRS'] for ds in ds_view})
    return out

def list_vms(content,tenant,vmtype=[vim.Folder]):
    ''' TODO:
        list nested vms
        show OS disk size and type
    '''
    #vm_obj = get_obj(content,vmtype,name)
    if tenant.startswith('/'):
        tenant = vc_tenant[1:]
    tenant_obj = content.searchIndex.FindByInventoryPath('DC01/vm/Tenants/'+tenant)
    vms = {}
    for vm in tenant_obj.childEntity:
        if hasattr(vm,"PowerOff"):
            if vm.summary.config.template:
                vms.update({vm.name:['t',vm.summary.config.numCpu,
                                        vm.summary.config.memorySizeMB,
                                        vm.summary.config.vmPathName.split()[0],
                                        vm.summary.config.guestFullName
                                        ]})
            else:
                info = vm_info(vm)
                vms.update({info[0]:['v',' '.join(info[1:])]})
                '''
                vms.update({vm.name:['v',vm.summary.config.numCpu,
                                        vm.summary.config.memorySizeMB,
                                        vm.summary.config.vmPathName.split()[0],
                                        vm.summary.config.guestFullName
                                     ]})
                '''
        else:
            vms.update({vm.name:['d']})
    return vms
    #return [vm.name for vm in vm_obj.childEntity if hasattr(vm,"PowerOff")]

def find_vm(content,name,vmtype=[vim.VirtualMachine]):
    vm = get_obj(content,vmtype,name)
    if vm:
        config = vm_info(vm)
        return {'v':[i for i in config]}
        '''
        return {'v':[vm.name,vm.summary.config.numCpu,
                                vm.summary.config.memorySizeMB,
                                vm.summary.config.vmPathName.split()[0],
                                vm.summary.config.guestFullName]}
        '''
    else:
        return None

def list_dvs(content,vmtype=[vim.DistributedVirtualSwitch]):
    obj = get_obj(content,vmtype)
    dvs = obj.view
    return [ switch.name for switch in dvs ]
       

def dvs_info(content,vmtype=[vim.DistributedVirtualSwitch],name=None):
    if not name:
        return 'No switch name provided'
    else:
        dvs = get_obj(content,vmtype,name)
        if not dvs:
            return 'No dvs with such name found'
        else:
            return dvs.summary.portgroupName

    
def get_templates_folder(content,vmtype=[vim.Folder],name='Templates'):
    folder = get_obj(content,vmtype,name)
    return folder

def list_templates(folder,temp_dict):
    if not hasattr(folder,'childEntity'):
        return temp_dict
    else:
        for obj in folder.childEntity:
            if hasattr(obj, 'PowerOff'):
                temp_dict.update({obj.name:obj.summary.config.guestFullName})
            else:
                list_templates(obj,temp_dict)
    return temp_dict

def clone(content,vm_name,vc_template,vc_tenant,vc_cluster,vc_datastore=None,power=False):
    if not vm_name:
        raise Exception("no vm name supplied")
    # desired cluster 
    cluster = get_obj(content, [vim.ClusterComputeResource], vc_cluster)
    # desired tenant
    # tenant = get_obj(content, [vim.Folder], vc_tenant)
    if vc_tenant.startswith('/'):
        vc_tenant = vc_tenant[1:]
    tenant = content.searchIndex.FindByInventoryPath('DC01/vm/Tenants/'+vc_tenant)
    # cluster and config specs
    resource_pool = cluster.resourcePool
    vmconf = vim.vm.ConfigSpec()

    # Storage DRS resourse
    if not vc_datastore:
        try:
            creds = vc_credentials(__credentials__)
        except FileNotFoundError:
            raise SystemExit('No .credentials file found')
        vc_datastore = creds['VC_DATASTORE']
 
    pod = get_obj(content, [vim.StoragePod], vc_datastore)
    if pod:
        podsel = vim.storageDrs.PodSelectionSpec()
        podsel.storagePod = pod

        storagespec = vim.storageDrs.StoragePlacementSpec()
        storagespec.podSelectionSpec = podsel
        storagespec.type = 'create'
        storagespec.folder = tenant
        storagespec.resourcePool = resource_pool
        storagespec.configSpec = vmconf

        try:
            rec = content.storageResourceManager.RecommendDatastores(storageSpec=storagespec)
            rec_action = rec.recommendations[0].action[0]
            real_datastore_name = rec_action.destination.name
        except:
            real_datastore_name = template.datastore[0].info.name
            datastore = get_obj(content, [vim.Datastore], real_datastore_name)
    else:
        real_datastore_name = vc_datastore
    datastore = get_obj(content, [vim.Datastore], real_datastore_name)

    # clone specs preparation
    relospec = vim.vm.RelocateSpec()
    relospec.datastore = datastore
    relospec.pool = resource_pool
    clonespec = vim.vm.CloneSpec()
    clonespec.location = relospec
    clonespec.powerOn = power

    template =  get_obj(content, [vim.VirtualMachine], vc_template)
    task = template.Clone(folder=tenant,name=vm_name,spec=clonespec)
    wait_for_task(task)

def vm_settings(content,vm_name,cpu,ram,hdd,epg=None,config=None):
    GiB = 1024*1024
    MiB = 1024

    ## expand disk
    disk = None
    vm = get_obj(content, [vim.VirtualMachine], vm_name)

    for device in vm.config.hardware.device:
        if isinstance(device, vim.vm.device.VirtualDisk):
            disk = device
            break
    if disk is None:
        raise Exception("Failed to find disk for VM")
    disk.capacityInKB = int(hdd) * GiB
    spec = vim.vm.ConfigSpec()
    devSpec = vim.vm.device.VirtualDeviceSpec(device=disk, operation="edit")
    spec.deviceChange.append(devSpec)
    wait_for_task(vm.Reconfigure(spec))

    """ Change cpu/ram settings """
    cspec = vim.vm.ConfigSpec()
    cspec.numCPUs = int(cpu)
    cspec.numCoresPerSocket = 1
    cspec.memoryMB = int(ram)*MiB
    task = vm.Reconfigure(cspec)
    wait_for_task(task)

    ''' Changing EPG settings '''
    if epg:
        device_change = []
        for device in vm.config.hardware.device:
            if isinstance(device, vim.vm.device.VirtualEthernetCard):
                nicspec = vim.vm.device.VirtualDeviceSpec()
                nicspec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
                nicspec.device = device
                nicspec.device.wakeOnLanEnabled = True
                network = get_obj(content,[vim.dvs.DistributedVirtualPortgroup],epg)
                dvs_port_connection = vim.dvs.PortConnection()
                dvs_port_connection.portgroupKey = network.key
                dvs_port_connection.switchUuid = network.config.distributedVirtualSwitch.uuid
                nicspec.device.backing = vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo()
                nicspec.device.backing.port = dvs_port_connection
                nicspec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
                nicspec.device.connectable.startConnected = True
                nicspec.device.connectable.allowGuestControl = True
                device_change.append(nicspec)
                break
        config_spec = vim.vm.ConfigSpec(deviceChange=device_change)
        task = vm.ReconfigVM_Task(config_spec)
        wait_for_task(task)

def add_disk(content, vm_name, disk_size, disk_type='thin'):
    vm = get_obj(content, [vim.VirtualMachine], vm_name)
    spec = vim.vm.ConfigSpec()
    unit_number = 0
    controller = None
    for dev in vm.config.hardware.device:
        if hasattr(dev.backing, 'fileName'):
            unit_number = int(dev.unitNumber) + 1
            if unit_number == 7:
                unit_number += 1
            if unit_number >= 16:
                print("we don't support this many disks")
                return
        if isinstance(dev, vim.vm.device.VirtualSCSIController):
            controller = dev

    # add disk here
    dev_changes = []
    new_disk_kb = int(disk_size) * 1024 * 1024
    disk_spec = vim.vm.device.VirtualDeviceSpec()
    disk_spec.fileOperation = "create"
    disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
    disk_spec.device = vim.vm.device.VirtualDisk()
    disk_spec.device.backing = vim.vm.device.VirtualDisk.FlatVer2BackingInfo()
    if disk_type == 'thin':
        disk_spec.device.backing.thinProvisioned = True
    disk_spec.device.backing.diskMode = 'persistent'
    disk_spec.device.unitNumber = unit_number
    disk_spec.device.capacityInKB = new_disk_kb
    disk_spec.device.controllerKey = controller.key
    dev_changes.append(disk_spec)
    spec.deviceChange = dev_changes
    task = vm.ReconfigVM_Task(spec=spec)
    wait_for_task(task)
