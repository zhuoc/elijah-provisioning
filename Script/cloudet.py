#!/usr/bin/env python
import xdelta3
import os, commands, filecmp, sys, subprocess, getopt
from datetime import datetime, timedelta

CUR_DIR = os.getcwd()

def diff_files(source_file, target_file, output_file):
    if os.path.exists(source_file) == False:
        print '[Error] No such file %s' % (source_file)
        return None
    if os.path.exists(target_file) == False:
        print '[Error] No such file %s' % (target_file)
        return None
    if os.path.exists(output_file) == True:
        os.remove(output_file)

    print '[INFO] create overlay comparing %s(base) and %s --> %s' % (os.path.basename(source_file), os.path.basename(target_file), os.path.basename(output_file))
    command_delta = ['xdelta3', '-f', '-s', source_file, target_file, output_file]
    ret = xdelta3.xd3_main_cmdline(command_delta)
    if ret == 0:
        return output_file
    else:
        return None

def merge_file(source_file, overlay_file, output_file):
    command_patch = ['xdelta3', '-d', '-s', source_file, overlay_file, output_file]
    ret = xdelta3.xd3_main_cmdline(command_patch)
    if ret == 0:
        return output_file
    else:
        return None

def compare_same(filename1, filename2):
    print '[INFO] checking validity of generated file'
    compare = filecmp.cmp(filename1, filename2)
    if compare == False:
        print '[ERROR] %s != %s' % (os.path.basename(filename1), os.path.basename(filename2))
        return False
    else:
        print '[INFO] SUCCESS to recover'
        return True

def create_overlay(base_image, base_mem):
    # generate overlay VM(disk + memory) from Base VM
    overlay_disk = None
    overlay_mem = None

    vm_name = os.path.basename(base_image).split('.')[0]
    vm_path = os.path.dirname(base_mem)
    overlay_disk = os.path.join(os.getcwd(), vm_name) + '_overlay.qcow2'
    overlay_mem = os.path.join(os.getcwd(), vm_name) + '_overlay.mem'
    tmp_disk = os.path.join(vm_path, vm_name) + '_tmp.qcow2'
    command_str = 'cp ' + base_image + ' ' + tmp_disk
    ret = commands.getoutput(command_str)

    print '[INFO] run Base Image to generate memory snapshot'
    run_snapshot(tmp_disk, base_mem)

    # migrate "exec:dd bs=1M 2> /dev/null | dd bs=1M of=ubuntu_base_tmp.mem 2> /dev/null" 
    tmp_mem = os.path.join(os.getcwd(), vm_name) + '_tmp.mem'
    if os.path.exists(tmp_mem) == False:
        print '[ERROR] new memory snapshot (%s) is not exit' % tmp_mem
        if os.path.exists(tmp_mem) == True:
            os.remove(tmp_mem)
        if os.path.exists(tmp_disk) == True:
            os.remove(tmp_disk)
        return None, None, None, None

    ret = diff_files(base_image, tmp_disk, overlay_disk)
    if ret == None:
        print '[ERROR] cannot create overlay disk'
        if os.path.exists(tmp_mem) == True:
            os.remove(tmp_mem)
        if os.path.exists(tmp_disk) == True:
            os.remove(tmp_disk)
        return None, None, None, None
    

    ret = diff_files(base_mem, tmp_mem, overlay_mem)
    if ret == None:
        print '[ERROR] cannot create overlay_mem'
        if os.path.exists(tmp_mem) == True:
            os.remove(tmp_mem)
        if os.path.exists(tmp_disk) == True:
            os.remove(tmp_disk)
        return None, None, None, None

    #os.remove(tmp_mem)
    #os.remove(tmp_disk)
    return overlay_disk, overlay_mem, tmp_disk, tmp_mem


def run_snapshot(disk_image, memory_image):
    command_str = "kvm -hda "
    command_str += disk_image
    command_str += " -m 512 -monitor stdio -enable-kvm -net nic -net user -serial none -parallel none -usb -usbdevice tablet -redir tcp:2222::22"
    command_str += " -incoming \"exec:cat " + memory_image + "\""
    print '[DEBUG] command : ' + command_str
    process = subprocess.Popen(command_str, shell=True)
    ret = process.wait()
    return ret


def create_base(imagefile):
    if os.path.exists(imagefile) == False:
        print '[ERROR] %s is not exist' % imagefile
        return None

    vm_name = os.path.basename(imagefile).split('.')[0]
    vm_path = os.path.dirname(imagefile)
    base_image = os.path.join(vm_path, vm_name) + '_base.qcow2'
    command_str = 'qemu-img create -f qcow2 -b ' + imagefile + ' ' + base_image
    ret = commands.getoutput(command_str)
    print '[INFO] run Base Image to generate memory snapshot'
    run_image(base_image)

    # migrate "exec:dd bs=1M 2> /dev/null | dd bs=1M of=ubuntu_base.mem 2> /dev/null" 
    base_mem = os.path.join(vm_path, vm_name) + '_base.mem'
    if os.path.exists(base_mem) == False:
        print '[ERROR] base memory snapshot (%s) is not exit' % base_mem
        return None, None

    return base_image, base_mem

def run_image(disk_image):
    command_str = "kvm -hda "
    command_str += disk_image
    command_str += " -m 512 -monitor stdio -enable-kvm -net nic -net user -serial none -parallel none -usb -usbdevice tablet -redir tcp:2222::22 "
    print "[Debug] command : ", command_str

    process = subprocess.Popen(command_str, shell=True)
    ret = process.wait()
    print "[Debug] run command : ", ret

def print_help(program_name):
    print 'help: %s...' % program_name

def print_usage(program_name):
    print 'usage: %s [option] [file]..  ' % program_name
    print ' -h, --help  print help'
    print ' -b, --base [disk image]'
    print ' -c, --create [base image] [base mem]'
    print ' -r, --run [base image] [base memory] [overlay image] [overlay memory]'


def main(argv):
    try:
        optlist, args = getopt.getopt(argv[1:], 'hbcr', ["help", "base", "create", "run"])
    except getopt.GetoptError, err:
        print str(err)
        print_usage(os.path.basename(argv[0]))
        sys.exit(2)

    # parse argument
    o = optlist[0][0]
    if o in ("-h", "--help"):
        print_help(os.path.basename(argv[0]))
    elif o in ("-b", "--base"):
        if len(args) != 1:
            print_help(os.path.basename(argv[0]))
            assert False, "Invalid argument"
        base_image, base_mem = create_base(args[0])
        print '[INFO] Base (%s, %s) is created from %s' % (base_image, base_mem, image_name)
    elif o in ("-c", "--create"):
        if len(args) != 2:
            print_help(os.path.basename(argv[0]))
            assert False, "Invalid argument"
        vm_image = args[0]
        vm_memory = args[1]
        # create overlay
        overlay_disk, overlay_mem, tmp_img, tmp_mem = create_overlay(base_image, base_mem)
        print '[INFO] Overlay (%s, %s) is created from %s' % (overlay_disk, overlay_mem, base_image)
        if os.path.exists(tmp_img) == True:
            os.remove(tmp_img)
        if os.path.exists(tmp_mem) == True:
            os.remove(tmp_mem)
    elif o in ("-r", "--run"):
        if len(args) != 4:
            print_help(os.path.basename(argv[0]))
            assert False, "Invalid argument"
        base_img = args[0], base_mem = args[1], overlay_img = args[2], overlay_mem = args[3]
        recover_img = os.path.join(os.path.dirname(base_img), 'recover.qcow2'); 
        recover_mem = os.path.join(os.path.dirname(base_mem), 'recover.mem');
        merge_file(base_img, overlay_img, recover_img)
        merge_file(base_mem, overlay_mem, recover_mem)
        run_snapshot(recover_img, recover_mem)
    else:
        assert False, "unhandled option"

    if len(optlist) == 0:
        print_usage(os.path.basename(argv[0]))
        sys.exit(2)


if __name__ == "__main__":
    main(sys.argv)