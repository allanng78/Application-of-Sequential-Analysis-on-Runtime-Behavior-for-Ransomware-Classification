import pandas as pd_read
import pandas as pd_write
import numpy as np
import cv2
from imutils import paths
import imutils
import argparse
import os
import shutil
import zipfile
import hashlib
import subprocess
from virus_total_apis import PublicApi as VirusTotalPublicApi

written = False


def extract_colour_historygram(image, bins=(32,32,32)):
    

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0,1,2], None, bins, [0, 256, 0, 256, 0, 256])
    if imutils.is_cv2():
        hist = cv2.normalize(hist)

    return hist.flatten()
	

	
def exractFeatureFromRegistry(processedData, header, for_record, col):
    reg = []
    reg = ['RegSetValue', 'RegDeleteKey', 'RegDeleteValue', 'SetSecurityFile']
    num_setvalue_reg = 0
    num_deletekey_reg = 0
    num_reg_value = {reg[0]:0, reg[1]:0, reg[2]:0, reg[3]:0}
    process_create = 'Process Create'
    num_process_create = 0
    process_create_list = []

    for i, r in enumerate(processedData[header[2]]): #operation column is selected
        if r == reg[0]:
            num_reg_value[reg[0]] = num_reg_value[reg[0]] + 1
        elif r == reg[1]:
            num_reg_value[reg[1]] = num_reg_value[reg[1]] + 1
        elif r == reg[2]:
            num_reg_value[reg[2]] = num_reg_value[reg[2]] + 1
        elif r == reg[3]:
            num_reg_value[reg[3]] = num_reg_value[reg[3]] + 1
        elif r == process_create:
            if processedData[header[0]][i] == 'python.exe':
                continue
            else:
                num_process_create = num_process_create + 1
                process_create_list.append(i)

        if isinstance(processedData[header[3]][i], basestring) == False: #check for NAN 
            continue

    for c in reg:
        col.append(c)		
        for_record[c]=num_reg_value[c]

    for_record['TotalReg']=  num_reg_value[reg[0]] + num_reg_value[reg[1]] + num_reg_value[reg[2]] + num_reg_value[reg[3]]  	
    col.append('TotalReg')
#    print 'reg set value : ', num_reg_value[reg[0]], '\n', '  reg delete key : ', num_reg_value[reg[1]]
#    print 'reg del value : ', num_reg_value[reg[2]], '\n', '  set security file : ', num_reg_value[reg[3]]
#    print 'There are ', for_record['TotalReg'], ' registry record'
	
    check = 0
    temp = processedData[header[3]][0]
    limits = 50  #len(processedData[header[3]])
    temp_check = np.zeros(len(processedData[header[3]]), dtype=bool)

	#-----------------------------Process Create feature---------------------------------------------------------
#    print '\n\n Number process created: ', num_process_create     #Display process create by the malware
#    print 'process created list'
#    for i in process_create_list:   
#        print processedData[header[3]][i] #, processedData[header[5]][i]

    for_record['ProcessCreate']=num_process_create
    col.append('ProcessCreate')
	
    return True

def check_for_encrypt_formate(full_path_file_name, file_name, format = '.zip'): # remove the encryption format
    dot_index = 0
    dot_index = full_path_file_name.rfind('.')
    if (file_name.count('.') > 1) and (format in file_name[:file_name.rfind('.')]): #check for encrypted file 
        return full_path_file_name[:dot_index]
    else:
        return full_path_file_name

def extractFeatureFromEncryption(mining_mtrix, processedData, header, for_record, col, format='.zip', num_of_file = 15):

    step_limit = num_of_file
    pos = 3
    encrypt_len = 0
#----------------------------------------------------------------------
    encrypt_cal_op = {'CreateFile': 25.6, 'SetDispositionInformationFile':51.2 \
               ,'SetRenameInformationFile':102.4, 'SetAllocationInformationFile':204.8}
    encrypt_cal_desired_access = {' Generic Read':0.2, ' Read Attributes':0.1, ' Read Control':0.4, ' Write Attributes':0.8, 'Write':1.6, ' Write Data':3.2, ' Generic Write':6.4, 'Add File':12.8,\
                               ' True':0.1, ' False':0.2}
    encrypt_cal_disposition =  {' Open':0.001, ' Close':0.002, ' OpenIf':0.004, ' OverwriteIf':0.008, ' Create':0.016, ' FileName':0.001}
    encrypt_cal_sharemode = {' None':0, ' Read':0.00001, ' Read Attributes':0.00002, ' Write':0.00004, ' Delete':0.00008}
    encrypt_cal_openresult = {' Opened':0.000001, ' Closed':0.000002, ' Created':0.000004}
 	   
#----------------------------------------------------------------------
 #   mining_mtrix = {}
    metrix_inddex = {}
    left_over = 0
    num_of_encryption_step = 0
    total_encrypt_len = []
    encrypt_format = False
    
#get 5 simples of zip 
    for i in range(len(processedData[header[pos]])):
        if isinstance(processedData[header[pos]][i], basestring) == False: #Skip the loop if not string
            continue

        full_path_file_name = processedData[header[pos]][i]
        index_num = processedData[header[pos]][i].rfind('\\') + 1 
        file_name = processedData[header[pos]][i][index_num:] 
		
        if len(mining_mtrix) < step_limit: 
            
            if format in file_name: #check the format from the last 4 char in the file name 
                
                processed_file_name = check_for_encrypt_formate(full_path_file_name, file_name, format)
					
                if (processed_file_name in mining_mtrix) == False: # if selected file name is not in matrix then add into first record
                    mining_mtrix[processed_file_name] = [i] #file name 
                    metrix_inddex[processed_file_name] = 1
                else:                                                # Add as subsequent record
                    mining_mtrix[processed_file_name].append(i)
                    metrix_inddex[processed_file_name] = metrix_inddex[processed_file_name] + 1
				
            if len(processedData[header[pos]]) == (i + 2): # Reach the end of the log and the mining matrix is still not fill n n
#                print len(processedData[header[pos]])
#                print 'insufficient mining', len(processedData[header[pos]]) 
                return False
            else:
                continue

 #       print 'length of mining_mtrix', mining_mtrix
		
        num_of_encryption_step = metrix_inddex[max(metrix_inddex, key = metrix_inddex.get)]
        if left_over == 0:
            for mining_i in mining_mtrix:
                #print 'in the matrix :', mining_i
                for num in range(1,num_of_encryption_step):
                    if len(mining_mtrix[mining_i]) < num + 1: #2: This is going in acsending 
                        left_over = left_over + (num_of_encryption_step - num) #2 This is going in decending 
                       # print 'left over : ', left_over
                        break 
				
        if (format in processedData[header[pos]][i]) == False:
            continue
            
        
  #      remove_format = check_for_encrypt_formate(full_path_file_name, file_name, format).rfind('.')
        file_name_done = check_for_encrypt_formate(full_path_file_name, file_name, format)

        for mined in mining_mtrix:
            if processedData[header[pos]][i] in mined: 
                mining_mtrix[file_name_done].append(i)
                metrix_inddex[file_name_done] = metrix_inddex[file_name_done] + 1
                left_over = left_over - 1
                break

        if left_over == 0:
           # print metrix_inddex
            break

    for num in mining_mtrix:
        total_encrypt_len.append(mining_mtrix[num][-1] - mining_mtrix[num][0] + 1)
#calculate the avg, max of encrypt length

    if len(mining_mtrix) > 0:
        if  len(mining_mtrix) == 1:
#            print 'Insufficient record for calculation'
            return False

        print 'encryption step :', len(mining_mtrix.values()[0])
#        print total_encrypt_len
        print 'encryption min length :', min(total_encrypt_len), 'encryption max length :', max(total_encrypt_len)
        print 'encryption mean :', np.mean(total_encrypt_len)
    
        for i in range(len(mining_mtrix.values()[0])):
#            print  total_encrypt_procedure[0][i], ': ', processedData[header[2]][total_encrypt_procedure[0][i]], "\t", processedData[header[3]][total_encrypt_procedure[0][i]]
            temp_detail = processedData[header[5]][mining_mtrix.values()[0][i]].split(',')
 #           print temp_detail
            point = encrypt_cal_op[processedData[header[2]][mining_mtrix.values()[0][i]]]
            for j in range(len(temp_detail)): #
                if ':' in temp_detail[j]: # Check for all :
                    temp = temp_detail[j].split(':')
                    if 'Desired Access' in temp[0]: 
                        if '/' in temp[1]:
                            read_write = temp[1].split('/')
                            #print 'read write', read_write[0], read_write[1], len(read_write)
                            point = point + encrypt_cal_desired_access[read_write[0]]
                            point = point + encrypt_cal_desired_access[read_write[1]]
                        else:
                            point = point + encrypt_cal_desired_access[temp[1]]			
                    elif 'Disposition' in temp[0]:
                        point = point + encrypt_cal_disposition[temp[1]]
                    elif 'ShareMode' in temp[0]:
                        point = point + encrypt_cal_sharemode[temp[1]]
                    elif 'OpenResult' in temp[0]:
                        point = point + encrypt_cal_openresult[temp[1]]
                    elif 'ReplaceIfExists' in temp[0]:
                        point = point + encrypt_cal_desired_access[temp[1]]
                    elif 'FileName' in temp[0]:
                        point = point + encrypt_cal_disposition[temp[0]]
                    elif 'Delete' in temp[0]:
                        point = point + encrypt_cal_desired_access[temp[1]] 
                elif 'Read' in temp_detail[j] or 'Write' in temp_detail[j]:
                    point = point + encrypt_cal_sharemode[temp_detail[j]]

            print i, ' Encryption point : ', point
            for_record['Enc'+str(i+1)] = point
            col.append('Enc'+str(i+1))
	
        if len(mining_mtrix.values()[0]) < 7:
            for i in range(len(mining_mtrix.values()[0])+1, 7):
                for_record['Enc'+str(i)] = 0 
                col.append('Enc'+str(i))

        for_record['EncryptionStep'] = len(mining_mtrix.values()[0])
        for_record['EncryptionMin'] = min(total_encrypt_len) 
        for_record['EncryptionMax'] = max(total_encrypt_len)
        for_record['EncryptionMean']= np.mean(total_encrypt_len)
        col.append('EncryptionStep')
        col.append('EncryptionMin')
        col.append('EncryptionMax')
        col.append('EncryptionMean')
        return True
    else:

        return False


#------------------------------Encryption History ------------------------------------------------------
#    print '\n Encryption History'

#for i in range(encrypt_len):
#    print  processedData[header[2]][encrypt_procedure[0] + i] , processedData[header[3]][encrypt_procedure[0] + i] #,  processedData[header[5]][encrypt_procedure[0] + i]

def white_list():

    white_list_info ={ 'README.HTML':'C:\\Program Files\\Common Files\\microsoft shared\\OFFICE15\\1033', \
                 'README.txt':'C:\\Program Files\\Java\\jre1.8.0_101', \
                  'THIRDPARTYLICENSEREADME-JAVAFX.txt':'C:\\Program Files\\Java\\jre1.8.0_101', \
                  'THIRDPARTYLICENSEREADME.txt':'C:\\Program Files\\Java\\jre1.8.0_101' }


def extractFeatureFromMsg(total_encrypt_procedure, processedData, header, for_record, col):
    msg_file = ''
    ransom_note_pos = 0
    point_file = 'NoribenReports.zip'
	# mining_mtrix.values()[0][0] # This is the first encrypted file position 
    point_dir =  processedData[header[3]][total_encrypt_procedure.values()[0][0]][:processedData[header[3]][total_encrypt_procedure.values()[0][0]].rfind('\\')].upper()
    store_msg = []
    got_msg = False
    is_msg = False # check whether the current file is a message file
	
	
#    print 'Check msg file.... Start from:',  processedData[header[3]][total_encrypt_procedure.values()[0][0]]
#    print 'point dir is :', point_dir
    for i in range(25):     #This is to extract the display file, for after the encryption of file in a folder
        if 	total_encrypt_procedure.values()[0][0] + i > len(processedData[header[3]]):
            break

        if isinstance(processedData[header[3]][total_encrypt_procedure.values()[0][0] + i], basestring):
            
            to_upper = processedData[header[3]][total_encrypt_procedure.values()[0][0] + i].upper()
            is_msg = False
            if ('HELP_' in to_upper) or \
                ('_HOWDO' in to_upper) or \
                ('RECOVER' in to_upper) or \
                ('README' in to_upper) or \
                ('RESTORE' in to_upper) or \
                ('_README' in to_upper) or \
                ('README_' in to_upper) or \
                ('DECRYPT' in to_upper) or \
                ('READ___ME' in to_upper) or \
                ('UPDATES' in to_upper) or \
                ('_READ_TH' in to_upper):
   #             print  total_encrypt_procedure.values()[0][0], 'Path passed first part:', to_upper
                if point_dir in to_upper: 
                    if (processedData[header[3]][total_encrypt_procedure.values()[0][0] + i] in store_msg):
                        continue
                    else:
                        store_msg.append(processedData[header[3]][total_encrypt_procedure.values()[0][0] + i])
 #                   print processedData[header[3]][total_encrypt_procedure[0][0] + i]

                    got_msg = True
                    is_msg = True
                    continue
		
            if (got_msg == True) and (is_msg == False):
                print 'There are ', len(store_msg), ' ransom message'
                for m in range(len(store_msg)):
                    temp = store_msg[m][store_msg[m].rfind('\\') + 1:]
                    print temp
                    msg_file = msg_file + ';' + temp
					
                ransom_note_pos = 2
                print 'Ransomware position: ', ransom_note_pos
                break
    
    htm_file = {}
    htm_different = {} #differences in name for file with same keyword
    htm_rear_file = {}
    htm_rear_different = {}
    htm_temp = {}
    htm_rear = []
    htm_file_loc = {}
    htm_rear_loc = {}
    jpg_file = {}
    jpg_different = {}
    jpg_temp = {}
    jpg_file_loc = {}
    jpg_rear_file = {}
    jpg_rear_different = {}
    jpg_rear_temp = []
    jpg_rear_loc = {}
    bmp_file = {}
    bmp_different = {}
    bmp_temp = {}
    bmp_file_loc = {}

    txt_file = {}
    txt_different = {}
    txt_temp = []
    txt_file_loc = {}
    txt_rear_file = {}
    txt_rear_temp = []
    txt_rear_different = {}
    txt_rear_loc = {}
	
    start_counting = 0
    if got_msg == False: #This is to retrieve the msg by checking each folder. In theory the ransom mnessage will have more file than other

        for file_ in processedData[header[3]]:
            if isinstance(file_, basestring):
                msg_index = file_.rfind('\\')
                text_len = len(file_)
                front_temp = file_[msg_index + 1: msg_index + 6]
                back_temp = file_[(text_len - 10):]

                if ('.htm' in file_) or ('.html' in file_) or ('.HTML' in file_):
                    if (front_temp in htm_file) == False:  # for the new record 
                        htm_file[front_temp] = 1
                        htm_file_loc[front_temp]= file_
                        htm_temp[front_temp] = [file_[msg_index + 1:]] #store the first file for different
                        htm_different[front_temp] = 0
                     
                    else:   #For existing file
                        htm_file[front_temp] = htm_file[front_temp] + 1
                        htm_file_loc[front_temp] = file_
						
                        if (file_[msg_index + 1:] in htm_temp[front_temp]) == False:  #
                            htm_different[front_temp] = htm_different[front_temp] + 1

                        htm_temp[front_temp].append(file_[msg_index + 1:])				
						
                    if (back_temp in htm_rear_file) == False:
                        htm_rear_file[back_temp] = 1
                        htm_rear_loc[back_temp]= file_
                    else:
                        htm_rear_file[back_temp] = htm_rear_file[back_temp] + 1
                        htm_rear_loc[back_temp] = file_	
			
						
                elif ('jpg' in file_) or ('png' in file_):
                    if (front_temp in jpg_file) == False:
                        jpg_file[front_temp] = 1
                        jpg_file_loc[front_temp]= file_
                        jpg_temp[front_temp] = [file_[msg_index + 1:]] #store the first file for different
                        jpg_different[front_temp] = 0
                    else:
                        jpg_file[front_temp] = jpg_file[front_temp] + 1
                        jpg_file_loc[front_temp] = file_    
						
                        if (file_[msg_index + 1:] in jpg_temp[front_temp]) == False:  #
                            jpg_different[front_temp] = jpg_different[front_temp] + 1

                        jpg_temp[front_temp].append(file_[msg_index + 1:])		
						
                    if (back_temp in jpg_rear_file) == False:
                        jpg_rear_file[back_temp] = 1
                        jpg_rear_loc[back_temp]= file_
                    else:
                        jpg_rear_file[back_temp] = jpg_rear_file[back_temp] + 1
                        jpg_rear_loc[back_temp] = file_	
						
                elif 'bmp' in file_:
                    if (front_temp in bmp_file) == False:
                        bmp_file[front_temp] = 1
                        bmp_file_loc[front_temp]= file_[msg_index + 1:]

                    else:
                        bmp_file[front_temp] = bmp_file[front_temp] + 1
                        bmp_file_loc[front_temp] = file_    						
						
                elif 'txt' in file_:
                    if (front_temp in txt_file) == False:
                        txt_file[front_temp] = 1
                        txt_file_loc[front_temp]= file_
                    else:
                        txt_file[front_temp] = txt_file[front_temp] + 1
                        txt_file_loc[front_temp] = file_

                    if (back_temp in txt_rear_file) == False:
                        txt_rear_file[back_temp] = 1
                        txt_rear_loc[back_temp]= file_
                    else:
                        txt_rear_file[back_temp] = txt_rear_file[back_temp] + 1
                        txt_rear_loc[back_temp] = file_						
		
        if (len(htm_file) == 0):
            htm_max = 0
            max_htm_label = 0
        else:
            htm_max = htm_file[max(htm_file, key=htm_file.get)]
            max_htm_label = max(htm_file, key=htm_file.get)
			
        if (len(htm_rear_file) == 0):
            htm_rear_max = 0
            max_htm_rear_label = 0
        else:
            htm_rear_max = htm_rear_file[max(htm_rear_file, key=htm_rear_file.get)]
            max_htm_rear_label = max(htm_rear_file, key=htm_rear_file.get) 

        if (len(jpg_file) == 0):
            jpg_max = 0
            max_jpg_label = 0
        else:
            jpg_max = jpg_file[max(jpg_file, key=jpg_file.get)]
            max_jpg_label = max(jpg_file, key=jpg_file.get)
			
        if (len(jpg_rear_file) == 0):
            jpg_rear_max = 0
            max_jpg_rear_label = 0
        else:
            jpg_rear_max = jpg_rear_file[max(jpg_rear_file, key=jpg_rear_file.get)]
            max_jpg_rear_label = max(jpg_rear_file, key=jpg_rear_file.get)      
						
        if (len(txt_file) == 0):
            txt_max = 0
            max_txt_label = 0
        else:
            txt_max = txt_file[max(txt_file, key=txt_file.get)]
            max_txt_label = max(txt_file, key=txt_file.get)
			
        if (len(txt_rear_file) == 0):
            txt_rear_max = 0
            max_txt_rear_label = 0
        else:
            txt_rear_max = txt_rear_file[max(txt_rear_file, key=txt_rear_file.get)]
            max_txt_rear_label = max(txt_rear_file, key=txt_rear_file.get)          
			
        max_occurance= { 'htm':htm_max,\
                             'jpg' : jpg_max,\
                             'txt' : txt_max}

        max_occurance_label= { 'htm':max_htm_label,\
                             'jpg' : max_jpg_label,\
                             'txt' : max_txt_label}
							 
        max_rear_occurance= { 'htm': htm_rear_max,\
                             'jpg' : jpg_rear_max,\
                             'txt' : txt_rear_max}

        max_rear_occurance_label= { 'htm': max_htm_rear_label,\
                                   'jpg' : max_jpg_rear_label,\
                                   'txt' : max_txt_rear_label}
			
      #  print 'max occurance:', max_occurance	
      #  print 'label :', 	max_occurance_label	
        #
        num_folder = 250   # Message is in every folder
		
        if (max_occurance['htm'] > num_folder) or (max_occurance['jpg'] > num_folder) or (max_occurance['txt'] > num_folder):
            if (max_occurance_label['htm'] == max_occurance_label['jpg']) and (max_occurance_label['htm'] == max_occurance_label['txt']):
                store_msg.append(htm_file_loc[max_occurance_label['htm']])
                store_msg.append(jpg_file_loc[max_occurance_label['jpg']])
                store_msg.append(txt_file_loc[max_occurance_label['txt']])
            elif max_occurance_label['htm'] == max_occurance_label['jpg']:
                store_msg.append(htm_file_loc[max_occurance_label['htm']])
                store_msg.append(jpg_file_loc[max_occurance_label['jpg']])
            elif max_occurance_label['htm'] == max_occurance_label['txt']:
                store_msg.append(htm_file_loc[max_occurance_label['htm']])
                store_msg.append(txt_file_loc[max_occurance_label['txt']])
            elif max_occurance_label['txt'] == max_occurance_label['jpg']:
                store_msg.append(txt_file_loc[max_occurance_label['txt']])
                store_msg.append(jpg_file_loc[max_occurance_label['jpg']])
            elif (max_occurance['htm'] > max_occurance['jpg']) and (max_occurance['htm'] > max_occurance['txt']):
                store_msg.append(htm_file_loc[max_occurance_label['htm']])
            elif (max_occurance['jpg'] > max_occurance['htm']) and (max_occurance['jpg'] > max_occurance['txt']):
                store_msg.append(jpg_file_loc[max_occurance_label['jpg']])		
            elif (max_occurance['txt'] > max_occurance['jpg']) and (max_occurance['txt'] > max_occurance['htm']):
                store_msg.append(txt_file_loc[max_occurance_label['txt']])	

            print 'store msg :', len(store_msg)			
            if len(store_msg)  > 0: 
                got_msg = True
        		
        elif (max_rear_occurance['htm'] > num_folder) or (max_rear_occurance['jpg'] > num_folder) or (max_rear_occurance['txt'] > num_folder):
            if max_rear_occurance_label['htm'] == max_rear_occurance_label['jpg'] and max_rear_occurance_label['htm'] == max_rear_occurance_label['txt']:
                store_msg.append(htm_rear_loc[max_rear_occurance_label['htm']])
                store_msg.append(jpg_rear_loc[max_rear_occurance_label['jpg']])
                store_msg.append(txt_rear_loc[max_rear_occurance_label['txt']])
            elif max_rear_occurance_label['htm'] == max_rear_occurance_label['jpg']:
                store_msg.append(htm_rear_loc[max_rear_occurance_label['htm']])
                store_msg.append(jpg_rear_loc[max_rear_occurance_label['jpg']])
            elif max_rear_occurance_label['htm'] == max_rear_occurance_label['txt']:
                store_msg.append(htm_rear_loc[max_rear_occurance_label['htm']])
                store_msg.append(txt_rear_loc[max_rear_occurance_label['txt']])
            elif max_rear_occurance_label['txt'] == max_rear_occurance_label['jpg']:
                store_msg.append(txt_rear_loc[max_rear_occurance_label['txt']])
                store_msg.append(jpg_rear_loc[max_rear_occurance_label['jpg']])
            elif (max_rear_occurance['htm'] > max_rear_occurance['jpg']) and (max_rear_occurance['htm'] > max_rear_occurance['txt']):
                store_msg.append(htm_rear_loc[max_rear_occurance_label['htm']])
            elif (max_rear_occurance['jpg'] > max_rear_occurance['htm']) and (max_rear_occurance['jpg'] > max_rear_occurance['txt']):
                store_msg.append(jpg_rear_loc[max_rear_occurance_label['jpg']])		
            elif (max_rear_occurance['txt'] > max_rear_occurance['jpg']) and (max_rear_occurance['txt'] > max_rear_occurance['htm']):
                store_msg.append(txt_rear_loc[max_rear_occurance_label['txt']])	
				
            print 'store msg :', len(store_msg)			
            if len(store_msg)  > 0: 
                got_msg = True
		
        if got_msg == True:
            print 'There are ', len(store_msg), ' ransom message'
            for m in range(len(store_msg)):
                temp = store_msg[m][store_msg[m].rfind('\\') + 1:]
                print temp
                msg_file = msg_file + ';' + temp
            ransom_note_pos = 2
            print 'Ransomware Position: ' , ransom_note_pos		
        elif len(htm_different) > 0: 
            if (htm_different[max(htm_different, key = htm_different.get)] > 10):
                store_msg.append(htm_temp[max(htm_different, key = htm_different.get)][0])
                for m in bmp_file:
                    if (m in htm_temp):
                        store_msg.append(bmp_file_loc[m])			

                msg_file = store_msg[0]
                msg_file = msg_file + ';' + store_msg[-1]
                ransom_note_pos = 3
                got_msg = True
                print 'There are ', len(store_msg), ' ransom message', store_msg
                print 'Ransomware Position: ' , ransom_note_pos		
            
			
    all_file = []
    all_num = []
    total_record = len(processedData[header[3]])
    first_few_file = 700 #For tweeting the config
    num_attempt = 0
	

    if got_msg == False: 
        while (len(store_msg) == 0):    
  #          print 'Step 1 and 2 fail. Continue with step 3.'
            for i, r in enumerate(processedData[header[2]]): #operation column is selected
                if r == 'CreateFile': 
                    index_num = processedData[header[3]][i].rfind('\\') + 1
                    if '.exe' in processedData[header[3]][i][index_num:]: #exclude exe file
                        continue			
			
                    if '.' in processedData[header[3]][i][index_num:]: # remove all folder
                        all_file.append(processedData[header[3]][i][index_num:])
 #           print processedData[header[3]][i]
             #   print all_file[-1]
            
                if (i == first_few_file):
                    break	
			
            temp_first_msg = []
            temp_first_msg.append(all_file[0])      #insert into temp 	
            all_file.remove(all_file[0])  #remove one record all_file after insert into temp
            temp_num = []
            temp_num.append(1)
            check_count = 0
            range_all_file = len(all_file)


            while 1:   #Search message from the first few file for the message display
                for i in range(range_all_file):
		 
                    if i ==  len(all_file): #Reach the end of the authored loop
                #print 'i : ', i, ' all file  :  ', len(all_file)
                        break
			
                    if i > len(all_file): 
                #print 'i > all file', len(all_file)
                        break
				
                    if temp_first_msg[check_count] == all_file[i]:
                        temp_num[check_count] = temp_num[check_count] + 1 # add one
                        all_file.remove(all_file[i]) # remove the file from all_file

                if len(all_file) == 0:            
                    break
			
        #print '1 end of file  :  ', len(all_file)
                check_count = check_count + 1
                temp_first_msg.append(all_file[0])
                temp_num.append(1)
                all_file.remove(all_file[0])
                range_all_file = len(all_file)
        #print '2 end of file  :  ', len(all_file)
            for i in range(len(temp_num)):
#        print temp[i], temp_num[i]
                if temp_num[i] == max(temp_num):
                    if '.htm' in temp_first_msg[i] or '.txt' in temp_first_msg[i] or '.png' in temp_first_msg[i]:
                        store_msg.append(temp_first_msg[i])
                        for m in range(len(store_msg)): # store the file name in the one variable 
                            temp_first_msg = store_msg[m][store_msg[m].rfind('\\') + 1:]
  #                      print temp
                            msg_file = msg_file + ';' + temp_first_msg
					
                        if len(store_msg) > 0:				
                            print 'There are ', len(store_msg), 'file for display message'
                            got_msg = True
                            ransom_note_pos = 1
                            print 'Ransomware position: ', ransom_note_pos             
                            print store_msg
                            break

            first_few_file = first_few_file + 200
            num_attempt = num_attempt + 1
            if (num_attempt == 3) or (len(store_msg) > 0):
                break
						
    htm = {}
    other = {}
	
    if got_msg == False: #check for msg store at the end. Most 
 #       print 'Step i, 2 and 3 fail. Continue with step 4.'
        for i in range(len(processedData[header[3]]), len(processedData[header[3]])/2):
            if processedData[header[2]] == 'CreateFile':
                temp = processedData[header[3]][processedData[header[3]].rfind('\\'):] 
                if len(htm[temp]) == 0: 
                    if 'HTML' in processedData[header[3]][i]:
                        htm[temp] = 1
                    else:
                        other[temp] = 1				   
                else:		
                    if 'HTML' in processedData[header[3]][i]:
                        htm[temp] = htm[temp] + 1
                    else:
                        other[temp] = other[temp] + 1

                if htm[temp] == 4:
                    store_msg.append(temp)
                    ransom_note_pos = 3
                    msg_file = temp
                    got_msg = True
                    break				
    if got_msg == False: 
        print 'There are ', 0, 'file for display message'  
        ransom_note_pos = 0
        print 'Ransomware position: ', ransom_note_pos	

    for_record['NumOfMsg']=len(store_msg)
    for_record['MsgFile']= msg_file
    for_record['MsgPos']=ransom_note_pos
    col.append('NumOfMsg')
    col.append('MsgFile')
    col.append('MsgPos')
	
def extractFeatureFromNet(processedData, header, for_record, col):
    network_com = 0
    network_TCP = 'TCP Receive'
    for tcp in processedData[header[2]]:
        if network_TCP in tcp:
            network_com = network_com + 1   
		
    for_record['TCPNetwork'] = network_com
    col.append('TCPNetwork')
	
def generate_MD5(filename, blocksize=65536):

	hash = hashlib.md5()
	
	with open(filename,"rb") as f:
		for block in iter(lambda: f.read(blocksize),b""):
			hash.update(block)
	
	return hash.hexdigest()
	
def VT_scan(file_path):
    API_KEY = '51adb8a913d592891086dc47f5bf627d18056d742f306f67458aa0885b2105ef'

    sample_MD5 = generate_MD5(file_path)

    vt = VirusTotalPublicApi(API_KEY)

    return vt.get_file_report(sample_MD5)
	
def process_pml_to_csv(procmonexe, pml_file, pmc_file, csv_file):
    """
    Uses Procmon to convert the PML to a CSV file

    Arguments:
        procmonexe: path to Procmon executable
        pml_file: path to Procmon PML output file
        pmc_file: path to PMC filter file
        csv_file: path to output CSV file
    Results:
        None
    """

    print('[*] Converting session to CSV: %s' % csv_file)
    cmdline = '"%s" /OpenLog "%s" /saveas "%s"' % (procmonexe, pml_file, csv_file)
    
    cmdline += ' /LoadConfig "%s"' % pmc_file
    #print('[*] Running cmdline: %s' % cmdline)
    stdnull = subprocess.Popen(cmdline)
    stdnull.wait()

	
	
def main(num, csv_path, image_path, pe_name, pe_file):				
#----------------------------------------------------------------------------
    mining_mtrix = {}
    dataset = csv_path
    print 'Read dataset : ', dataset
    data = pd_read.read_csv(dataset)
    processedData = data.drop(['Time of Day'], axis=1) 
    header = []
    global written
    num_of_file = 8

    imagePath = image_path
    image = cv2.imread(imagePath)


#----------------------------------------------------------
    for h in processedData:
        header.append(h)

    col = [] #column for the dataframe
    for_record = {}
#-------------------------- registry feature---------------------------------------------------------
    status = exractFeatureFromRegistry(processedData, header, for_record, col)
		
#---------------------------------------------Encryption feature---------------------------------------------------------
    status = extractFeatureFromEncryption(mining_mtrix, processedData, header, for_record, col, '.zip')
    
    format_analysis = ['.docx', '.jpg']
	
    for i in range(len(format_analysis)):
        if status == False:
            print 'mine ', format_analysis[i]
            mining_mtrix = {}
            status = extractFeatureFromEncryption(mining_mtrix, processedData, header, for_record, col, format_analysis[i], num_of_file)
        else:
            break
	
    if status == False:
#        print 'No encryption feature'
        for_record['EncryptionStep'] = 0
        for_record['EncryptionMin'] = 0
        for_record['EncryptionMax'] = 0
        for_record['EncryptionMean']= 0
        col.append('EncryptionStep')
        col.append('EncryptionMin')
        col.append('EncryptionMax')
        col.append('EncryptionMean')
        for_record['NumOfMsg']=0
        for_record['MsgPos']=0
        col.append('NumOfMsg')
        col.append('MsgPos')
    else:
#------------------------------display_message feature---------------------------------------------------------
        extractFeatureFromMsg(mining_mtrix, processedData, header, for_record, col)
        extractFeatureFromNet(processedData, header, for_record, col)

    csv_file = ''
    head = False
    success_ = False
	
    if status == False:
        csv_file = 'fail.csv'
    else:
        csv_file = args.output
        success_ = True
        dest_dir = image_path[:image_path.rfind('\\')] + '\\ransomware_image'
        #print dest_dir
        image_file = image_path[image_path.rfind('\\')+1:]
        #print image_file
        if not os.path.exists(dest_dir):
            print 'There is no image directory'
            os.makedirs(dest_dir)
        destination = dest_dir + '\\' + image_file

        if os.path.exists(destination):
            print 'The image exist in dest folder'
        else:
            shutil.move(image_path, destination)
   
        if os.path.exists(pe_file):
            des = VT_scan(pe_file)
		
            col.append('Symantec')
            col.append('TrendMicro')
            col.append('Kaspersky')
            col.append('McAfee')
            col.append('BitDefender')
            col.append('F-Secure')
            col.append('FData')
		
            if 'results' in des:
                if 'scans' in des['results']:
                    if 'Symantec' in des['results']['scans']:
                        for_record['Symantec'] = des['results']['scans']['Symantec']['result']            
                        print 'Symantec', for_record['Symantec']
                    else: 
                        for_record['Symantec'] = 'NA'
                    if 'TrendMicro' in des['results']['scans']:
                        for_record['TrendMicro'] = des['results']['scans']['TrendMicro']['result']              
                        print 'TrendMicro', for_record['TrendMicro']
                    else:
                        for_record['TrendMicro'] = 'NA'
                    if 'Kaspersky' in des['results']['scans']:
                        for_record['Kaspersky'] = des['results']['scans']['Kaspersky']['result']             
                        print 'Kaspersky', for_record['Kaspersky']
                    else:
                        for_record['Kaspersky'] = 'NA'
                    if 'McAfee' in des['results']['scans']:
                        for_record['McAfee'] = des['results']['scans']['McAfee']['result']           
                        print 'McAfee', for_record['McAfee']
                    else:
                        for_record['McAfee'] = 'NA'
                    if 'BitDefender' in des['results']['scans']:
                        for_record['BitDefender'] = des['results']['scans']['BitDefender']['result']           
                        print 'BitDefender', for_record['BitDefender']
                    else:
                        for_record['BitDefender'] = 'NA'
                    if 'F-Secure' in des['results']['scans']:
                        for_record['F-Secure'] = des['results']['scans']['F-Secure']['result']           
                        print 'F-Secure', for_record['F-Secure']
                    else:
                        for_record['F-Secure'] = 'NA'
                    if 'FData' in des['results']['scans']:
                        for_record['FData'] = des['results']['scans']['FData']['result']           
                        print 'FData', for_record['FData']
                    else:
                        for_record['FData'] = 'NA'						

                else:
                    for_record['Symantec'] = 'NA'
                    for_record['TrendMicro'] = 'NA'
                    for_record['Kaspersky'] = 'NA'
                    for_record['McAfee'] = 'NA'
                    for_record['BitDefender'] = 'NA'
                    for_record['F-Secure'] = 'NA'
                    for_record['FData'] = 'NA'

        else: 
            print 'No PE result'
	
    if success_ == True:
        if args.header == True and written == False:
            head = True
            written = True
            print '\n\nheader :', head, written,'\n\n'
        else:
            head = False
		
        
	 
    record = pd_write.DataFrame(for_record, columns = col, index = [pe_name])
    record.to_csv(csv_file, header=head, mode='a')
		
def findFile(filepath):   
    if os.path.exists(filepath):
        return True
    else:
        return False

if __name__ == '__main__':
	
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', help='filename', required=False)
    parser.add_argument('--dir', help='Run all executables from a specified directory', required=False)
    parser.add_argument('--output',  help='output folder', required=False)
    parser.add_argument('--header', action='store_true',  help='Add header to csv file', required=False)
    args = parser.parse_args()
    
    list_of_zip = []
    list_of_image = []
    list_of_pe = []
    pe_name = ''
    sel_pe = ''
 

    for f in os.listdir(args.dir):
        if not os.path.isdir(args.dir + '\\' + f):
           
            #temp = f[f.rfind('.'):]
            #print 'temp : ' , temp
            
            if '.zip' in f:
            #    print 'in zip', f
                list_of_zip.append(args.dir + '\\' + f)
            elif '.png' in f:
           #     print 'in pic', f
                list_of_image.append(args.dir + '\\' + f)
            elif '.exe' in f or '.bin' in f:
                list_of_pe.append(args.dir + '\\' + f)               
         
	
    for num, zip_file in enumerate(list_of_zip): #Check for image and pe file same name as the zip
        # Create folder
        print '\n Recored', num+1, '\n'
        
        image_found = False
        pe_found = False
        #print 'Header :    ', args.header
        zipFile = zip_file[:zip_file.rfind('_')]
        for pic_file in list_of_image:
            if zipFile in pic_file:
 #               print 'image file found:', pic_file
                sel_image = pic_file
                image_found = True
                break
        for pe in list_of_pe:
            if zipFile in pe:
 #               print 'PE found'
                sel_pe = pe
                pe_found = True
                break
				
				
        if image_found == False:
 #           print 'image not found'
            continue
		
        dest_dir = zip_file[:zip_file.rfind('_')]
        pe_name = zip_file[zip_file.rfind('\\') + 1 :zip_file.rfind('_')]
        print 'zip folder: ', zip_file
		
        try:
            zfile = zipfile.ZipFile(zip_file, 'r') # Create ZipFile
        except:
            print 'Bad zip file'
            continue
        
        if not os.path.exists(dest_dir):
 #           print 'There is no directory'
            os.makedirs(dest_dir)
         
        elif not os.path.isdir(dest_dir): #If the file is not a directory
 #           print 'This is a file not directory'
            if os.path.exists(dest_dir+ '.bin'): 
                os.remove(dest_dir)
            else:
                os.rename(dest_dir, dest_dir + '.bin') #Rename this file with a format
                if pe_found == False:
	                sel_pe =  dest_dir + '.bin' #sel file will be assigned to a newly change file
            os.makedirs(dest_dir)
			
        zfile.extractall(dest_dir)   
			
        for file_name in os.listdir(dest_dir):
 #           print 'Filename:   ', file_name
            if ('.csv' in file_name) and ('timeline' not in file_name) and ('Noriben_29_Nov_17__11_03_40_397000' not in file_name):
 #               print 'name csv found :', file_name 
					
                temp_file = file_name[file_name.rfind('.'):]
            
#                print 'dest dir: ', dest_dir, '\\', name
                main(num, dest_dir+'\\'+ file_name, sel_image, pe_name, sel_pe) #, sel_image)
                break
				
		
						
						
												

