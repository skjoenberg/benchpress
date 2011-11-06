/*
 * Copyright 2011 Troels Blum <troels@blum.dk>
 *
 * This file is part of cphVB <http://code.google.com/p/cphvb/>.
 *
 * cphVB is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * cphVB is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with cphVB. If not, see <http://www.gnu.org/licenses/>.
 */

#include <iostream>
#include <stdexcept>
#include <cuda.h>
#include <cphvb.h>
#include "cphvb_ve_cuda.h"
#include "PTXopcode.h"
#include "Configuration.hpp"

InstructionScheduler* instructionScheduler;
DeviceManager* deviceManager;

cphvb_error cphvb_ve_cuda_init( cphvb_intp *opcode_count,
                                cphvb_opcode opcode_list[],
                                cphvb_intp *datatype_count,
                                cphvb_type datatype_list[],
                                cphvb_com *self)
{
    *opcode_count = 0;
    for (cphvb_opcode oc = 0; oc < CPHVB_NO_OPCODES; ++oc)
    {
        if (ptxOpcodeMap(oc) >= 0)
        {
            opcode_list[*opcode_count] = oc;
            ++*opcode_count;
        }
    }

    //TODO create propper list of supported reduce functions
    opcode_list[*opcode_count] = CPHVB_ADD | CPHVB_REDUCE;
    ++*opcode_count;
    
    datatype_list[0] = CPHVB_FLOAT32;
    datatype_list[1] = CPHVB_BOOL;
    *datatype_count = 2;

    try {
        deviceManager = createDeviceManager();
        deviceManager->initDevice(0);
        MemoryManager* memoryManager = createMemoryManager();
        DataManager* dataManager = createDataManager(memoryManager);
        KernelGenerator* kernelGenerator = createKernelGenerator();
        instructionScheduler = createInstructionScheduler(dataManager,
                                                          kernelGenerator);
    } 
    catch (std::exception& e)
    {
        std::cerr << e.what() << std::endl;
        return CPHVB_ERROR;
    }
    return CPHVB_SUCCESS;
}

cphvb_error cphvb_ve_cuda_execute(cphvb_intp instruction_count,
                                  cphvb_instruction instruction_list[])
{
    try 
    {
        instructionScheduler->schedule(instruction_count,
                                       (cphVBinstruction*)instruction_list);
    }
    catch (std::exception& e)
    {
        std::cerr << e.what() << std::endl;
        return CPHVB_ERROR;
    }
    return CPHVB_SUCCESS;
}

cphvb_error cphvb_ve_cuda_shutdown()
{
    try 
    {
        instructionScheduler->flushAll();
    }
    catch (std::exception& e)
    {
        std::cerr << e.what() << std::endl;
        return CPHVB_ERROR;
    }
    return CPHVB_SUCCESS;
}
