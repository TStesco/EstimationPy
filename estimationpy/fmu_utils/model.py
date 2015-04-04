'''
Created on Sep 6, 2013

@author: marco
'''

import pyfmi
import numpy
import pandas as pd
import datetime

from estimationpy.fmu_utils.in_out_var import InOutVar
from estimationpy.fmu_utils.tree import Tree
from estimationpy.fmu_utils.estimation_variable import EstimationVariable

import estimationpy.fmu_utils.strings as fmu_util_strings

class Model():
    """
    
    This class contains a reference to a particular FMU that has been loaded into the tool.
    For this FMU, several information are collected together. These information describe what to do with the FMU in 
    the future steps.
    
    A list of:
    
    - parameters,
    - and state variables
    
    that will be estimated/identified.
    
    A list of:
    
    - inputs data series,
    - and output data series
    
    that will be used for simulating the FMU and comparing results.
    
    """
    
    def __init__(self, fmuFile = None, result_handler = None, solver = None, atol = 1e-6, rtol = 1e-4, setTrees = False, verbose = None):
        """
        
        Constructor of the class Model.
        
        """
        
        # Reference to the FMU, that will be loaded using pyfmi
        self.fmu = None
        self.fmuFile = fmuFile
        # List of parameters
        self.parameters = []
        # List of state variables
        self.variables = []
        # List of inputs
        self.inputs = []
        # List of outputs
        self.outputs = []
        
        # Initialize the properties of the FMU
        self.name = ""
        self.author = ""
        self.description = ""
        self.type = ""
        self.version = ""
        self.guid = ""
        self.tool = ""
        self.numStates = ""
        
        # Trees that describe parameters, state variables, inputs and outputs hierarchy
        self.treeParameters = Tree(fmu_util_strings.PARAMETER_STRING)
        self.treeVariables = Tree(fmu_util_strings.VARIABLE_STRING)
        self.treeInputs = Tree(fmu_util_strings.INPUT_STRING)
        self.treeOutputs = Tree(fmu_util_strings.OUTPUT_STRING)
        
        # Number of maximum tries for a simulation to be successfully run
        self.SIMULATION_TRIES = 4
        
        # Empty dictionary that will contain the simulation options
        self.opts = {}
        
        # Set the number of states
        self.N_STATES = 0
        
        # An array that contains the value references for every state variable
        self.stateValueReferences = []
        
        # See what can be done in catching the exception/propagating it
        if fmuFile != None:
            self.__set_fmu__(fmuFile, result_handler, solver, atol, rtol, verbose)
            if setTrees:
                self.__set_trees__()
    
    def add_parameter(self, obj):
        """
        This method add one object to the list of parameters. This list contains only the parameters that 
        will be modified during the further analysis
        """
        if self.is_parameter_present(obj):
            print "Parameter: ", obj, " not added, already present"
            return False
        else:
            # the object is not yet part of the list, add it            
            par = EstimationVariable(obj, self)
            self.parameters.append(par)
            print "Added variable: ",obj," (",par,")"
            
            return True
    
    def add_variable(self, obj):
        """
        This method add one object to the list of variables. This list contains only the variables that 
        will be modified during the further analysis
        """
        if self.is_variable_present(obj):
            print "Variable: ", obj, " not added, already present"
            return False
        else:
            # the object is not yet part of the list, add it
            # but before embed it into an EstimationVariable class
            var = EstimationVariable(obj, self)
            self.variables.append(var)
            print "Added variable: ",obj," (",var,")"
            return True
    
    def check_input_data(self, align = True):
        """
        This method check if all the input data are ready to be used or not. If not because they are not aligned, this method
        tries to correct them providing an interpolation
        """
        return self.check_data_list(self.inputs, align)
    
    def check_data_list(self, dataList, align = True):
        """
        This method check if all the data series provided by the dataList are ready to be used or not.
        If not because they are not aligned, this method tries to correct them providing an interpolation
        """
        # TODO: Done
        
        # Create a list of data series, one for each input
        dataSeries = []
        for inp in dataList:
            dataSeries.append(inp.get_data_series())
        
        Ninputs = len(dataSeries)
        Tmin = 0.0
        Tmax = 0.0
        Npoints = 0
        match = True
        
        # Scan all the data series
        for i in range(Ninputs):
            
            if i == 0:
                Tmin = dataSeries[i].index[0]
                Tmax = dataSeries[i].index[-1]
            else:
                if not dataSeries[i].index.tolist() == dataSeries[i-1].index.tolist():
                    match = False
                    Tmin = max(Tmin, dataSeries[i].index[0])
                    Tmax = min(Tmax, dataSeries[i].index[-1])
        
        # Check if they match or not           
        if match == False and align:
            
            # At the end of this loop we know
            # which data series has the bigger number of points and will
            # be used as base for the other ones
            MaxPoints = 0
            ind = 0
            for i in range(Ninputs):
                NumP = len(dataSeries[i].ix[0])
                if NumP > MaxPoints:
                    MaxPoints = NumP
                    ind = i
            
            # Select the best index
            new_index = dataSeries[ind].index
            
            # Interpolate using the same datetimeIndex
            for inp in dataList:
                inp.get_data_series().reindex(new_index).interpolate(method='linear')
                
            return False
        else:
            print "\tMatch between data series - OK"
            return True

    def get_constr_obs_states_high(self):
        """
        This method returns an array of boolean flags that indicate if an observed state variable is either
        constrained or not
        """
        constrHi = numpy.empty(self.get_num_variables())
        i = 0
        for v in self.variables:
            constrHi[i] = v.get_constraint_high()
            i += 1
        return constrHi
    
    def get_constr_obs_states_low(self):
        """
        This method returns an array of boolean flags that indicate if an observed state variable is either
        constrained or not
        """
        constrLow = numpy.empty(self.get_num_variables())
        i = 0
        for v in self.variables:
            constrLow[i] = v.get_constraint_low()
            i += 1
        return constrLow
    
    def get_constr_pars_high(self):
        """
        This method returns an array of boolean flags that indicate if an estimated parameter is either
        constrained or not
        """
        constrHi = numpy.empty(self.get_num_parameters())
        i = 0
        for p in self.parameters:
            constrHi[i] = p.get_constraint_high()
            i += 1
        return constrHi
    
    def get_constr_pars_low(self):
        """
        This method returns an array of boolean flags that indicate if an estimated parameter is either
        constrained or not
        """
        constrLow = numpy.empty(self.get_num_parameters())
        i = 0
        for p in self.parameters:
            constrLow[i] = p.get_constraint_low()
            i += 1
        return constrLow
    
    def get_cov_matrix_states(self):
        """
        This method returns the covariance matrix of the state variables
        """
        cov = numpy.diag(numpy.zeros(self.get_num_variables()))
        i = 0
        for v in self.variables:
            cov[i,i] = v.get_covariance()
            i += 1
        return cov
    
    def get_cov_matrix_state_pars(self):
        """
        This method returns the covariance matrix of the state variables and parameters
        """
        cov = numpy.diag(numpy.zeros(self.get_num_variables() + self.get_num_parameters()))
        i = 0
        for v in self.variables:
            cov[i,i] = v.get_covariance()
            i += 1
        for p in self.parameters:
            cov[i,i] = p.get_covariance()
            i += 1
        return cov
    
    def get_cov_matrix_parameters(self):
        """
        This method returns the covariance matrix of the parameters
        """
        cov = numpy.diag(numpy.zeros(self.get_num_parameters()))
        i = 0
        for p in self.parameters:
            cov[i,i] = p.get_covariance()
            i += 1
        return cov
    
    def get_cov_matrix_outputs(self):
        """
        This method returns the covariance matrix of the outputs
        """
        cov = numpy.diag(numpy.zeros(self.get_num_measured_outputs()))
        i = 0
        for o in self.outputs:
            if o.is_measured_output():
                cov[i,i] = o.get_covariance()
                i += 1
        return cov
          
    def get_fmu(self):
        """
        This method return the FMU associated to the model
        """
        return self.fmu
    
    def get_fmu_file_path(self):
        """
        This method returns the filepath of the FMU
        """
        return self.fmuFile
    
    def get_fmu_name(self):
        """
        This method returns the name of the FMU associated to the model
        """
        return self.name
    
    def get_inputs(self):
        """
        Return the list of input variables associated to the FMU that have been selected
        """
        return self.inputs
    
    def get_input_by_name(self, name):
        """
        This method returns the input contained in the list of inputs that has a name equal to 'name'
        """
        for var in self.inputs:
            if var.get_object().name == name:
                return var
        return None
    
    def get_input_names(self):
        """
        This method returns a list of names for each input
        """
        inputNames = []
        for inVar in self.inputs:
            # inVar is of type InOutVar and the object that it contains is a PyFMI variable
            inputNames.append(inVar.get_object().name)
        return inputNames
    
    def get_input_readers(self, t):
        """
        This method returns a list of functions that read the input for a given time
        """
        # TODO
        outputs = []
        for inVar in self.inputs:
            # inVar is of type InOutVar and the object that it contains is a PyFMI variable
            outputs.append(inVar.read_from_data_series(t))
        return outputs
    
    def get_inputs_tree(self):
        """
        This method returns the tree associated to the inputs of the model
        """
        return self.treeInputs
    
    def get_measured_outputs_values(self):
        """
        This method return a vector that contains the values of the observed state variables of the model
        That are listed in self.variables
        """
        obsOut = numpy.zeros(self.get_num_measured_outputs())
        i = 0
        for o in self.outputs:
            if o.is_measured_output():
                obsOut[i] = o.read_value_in_fmu(self.fmu)
                i += 1
        return obsOut
    
    def get_measured_data_ouputs(self, t):
        """
        This method returns the measured data value of the observed outputs at a given time
        instant t, that is a datetime object/string part of the datetimeIndex of the pandas.Series
        """
        # TODO: Done
        obsOut = numpy.zeros(shape=(1, self.get_num_measured_outputs()))
        i = 0
        for o in self.outputs:
            if o.is_measured_output():
                obsOut[0,i] = o.read_from_data_series(t)
                i += 1
        return  obsOut
    
    def get_measured_output_data_series(self):
        """
        This method returns the data series associated to each measured output
        """
        # TODO: Done
        # Get all the data series from the CSV files (for every input of the model)
        outDataSeries = []
        for o in self.outputs:
            if o.is_measured_output():
                outDataSeries.append(o)
        
        # Try to align the measured output data
        self.check_data_list(outDataSeries, align = True)
        
        # Now transform it into a matrix with time as first column and the measured outputs
        time = outDataSeries[0].get_data_series().index
        
        # Create the empty matrix
        Npoints = len(time)
        Nouts = self.get_num_measured_outputs()
        dataMatrix = numpy.zeros(shape=(Npoints, Nouts+1))
        
        # Define the first column as the time
        dataMatrix[:,0] = time
        
        # Put the other values in the following columns
        i = 1
        for o in outDataSeries:
            dataMatrix[:,i] = o.get_data_series().values
            i += 1
        
        return dataMatrix 
    
    def get_num_inputs(self):
        """
        This method returns the total number of input variables of the FMU model
        """
        return len(self.inputs)
    
    def get_num_outputs(self):
        """
        This method returns the total number of output variables of the FMU model
        """
        return len(self.outputs)
    
    def get_num_measured_outputs(self):
        """
        This method returns the number of measured output variables of the FMU model
        """
        i = 0
        for o in self.outputs:
            if o.is_measured_output():
                i += 1
        return i
    
    def get_num_parameters(self):
        """
        This method returns the number of parameters of the FMU model to be estimated or identified
        """
        return len(self.parameters)
    
    def get_num_variables(self):
        """
        This method returns the number of variables of the FMU model to be estimated or identified
        """
        return len(self.variables)
    
    def get_num_states(self):
        """
        This method returns the total number of states variables of the FMU model
        """
        return self.N_STATES
    
    def get_outputs(self):
        """
        Return the list of output variables associated to the FMU that have been selected
        """
        return self.outputs
    
    def get_output_by_name(self, name):
        """
        This method returns the output contained in the list of outputs that has a name equal to 'name'
        """
        for var in self.outputs:
            if var.get_object().name == name:
                return var
        return None
    
    def get_output_names(self):
        """
        This method returns a list of names for each output
        """
        outputNames = []
        for outVar in self.outputs:
            # outVar is of type InOutVar and the object that it contains is a PyFMI variable
            outputNames.append(outVar.get_object().name)
        return outputNames
    
    def get_outputs_values(self):
        """
        This method return a vector that contains the values of the outputs of the model
        """
        obsOut = numpy.zeros(self.get_num_outputs())
        i = 0
        for o in self.outputs:
            obsOut[i] = o.read_value_in_fmu(self.fmu)
            i += 1
        return obsOut
    
    def get_outputs_tree(self):
        """
        This method returns the tree associated to the outputs of the model
        """
        return self.treeOutputs
    
    def get_parameters(self):
        """
        Return the list of parameters contained by the FMU that have been selected
        """
        return self.parameters
    
    def get_parameters_min(self):
        """
        This method return a vector that contains the values of the min value possible for the estimated parameters
        """
        minValues = numpy.zeros(self.get_num_parameters())
        i = 0
        for p in self.parameters:
            minValues[i] = p.get_min_value()
            i += 1
        return minValues
    
    def get_parameters_max(self):
        """
        This method return a vector that contains the values of the max value possible for the estimated parameters
        """
        maxValues = numpy.zeros(self.get_num_parameters())
        i = 0
        for p in self.parameters:
            maxValues[i] = p.get_max_value()
            i += 1
        return maxValues
    
    def get_parameter_names(self):
        """
        This method returns a list of names for each state variables observed
        """
        parNames = []
        for par in self.variables:
            # EstimationVariable
            parNames.append(par.name)
        return parNames
    
    def get_parameter_values(self):
        """
        This method return a vector that contains the values of the observed state variables of the model
        That are listed in self.variables
        """
        obsPars = numpy.zeros(self.get_num_parameters())
        i = 0
        for p in self.parameters:
            obsPars[i] = p.read_value_in_fmu(self.fmu)
            i += 1
        return obsPars
    
    def get_parameters_tree(self):
        """
        This method returns the tree associated to the parameters of the model
        """
        return self.treeParameters
    
    def get_properties(self):
        """
        This method returns a tuple containing the properties of the FMU
        """
        return (self.name, self.author, self.description, self.type, self.version, self.guid, self.tool, self.numStates)
    
    def get_real(self, var):
        """
        Get a real variable in the FMU model, given the PyFmi variable description
        """
        return self.fmu.get_real(var.value_reference)[0]
    
    def get_simulation_options(self):
        """
        This method returns the simulation options of the simulator
        """
        return self.opts
    
    def get_state(self):
        """
        This method return a vector that contains the values of the entire state variables of the model
        """
        return self.fmu._get_continuous_states()
    
    def get_state_observed_values(self):
        """
        This method return a vector that contains the values of the observed state variables of the model
        That are listed in self.variables
        """
        obsState = numpy.zeros(self.get_num_variables())
        i = 0
        for v in self.variables:
            obsState[i] = v.read_value_in_fmu(self.fmu)
            i += 1
        return obsState
    
    def get_state_observed_min(self):
        """
        This method return a vector that contains the values of the min value possible for the observed states
        """
        minValues = numpy.zeros(self.get_num_variables())
        i = 0
        for v in self.variables:
            minValues[i] = v.get_min_value()
            i += 1
        return minValues
    
    def get_state_observed_max(self):
        """
        This method return a vector that contains the values of the max value possible for the observed states
        """
        maxValues = numpy.zeros(self.get_num_variables())
        i = 0
        for v in self.variables:
            maxValues[i] = v.get_max_value()
            i += 1
        return maxValues
    
    def get_tree(self, objectTree, variability, causality, onlyStates = False, pedantic = False):
        """
        This function, provided one tree, populates it.
        The tree is used to represent the parameters, variables, input, outputs with the dot notation,
        and used as support for the graphical object tree
        """
        try:
            
            # Take the variable of the FMU that have the specified variability and causality
            # the result is a dictionary which has as key the name of the variable with the dot notation
            # and as element a class of type << pyfmi.fmi.ScalarVariable >>
            # Alias variable removed for clarity.
            dictParameter = self.fmu.get_model_variables(include_alias = False, variability = variability, causality = causality)
            
            if onlyStates and pedantic:
                print "Ref. values of the states: "+str(self.stateValueReferences)
            
            for k in dictParameter.keys():
                ####################################################################################
                # TODO: check if it's true to don't add now the variables which have derivatives
                #       I think in general is not true, but be careful with the extraction of the 
                #       name with the dot notation
                ####################################################################################
                if "der(" not in k:
                    
                    # Split the variable name that is written with the dot notation
                    strNames = k.split(".")
                    
                    # Given the vector of names obtained with the dot notation creates the branches of the tree
                    # and name correctly each node and leaf.
                    #
                    # The object attached to each leaf of the tree is << dictParameter[k] >>
                    # which is of type << pyfmi.fmi.ScalarVariable >>
                    if onlyStates:
                        
                        # Add the variables that are in the state vector of the system
                        if dictParameter[k].value_reference in self.stateValueReferences:
                            objectTree.addFromString(strNames, dictParameter[k])
                            if pedantic:
                                print str(k) + " with Ref. value =" + str(dictParameter[k].value_reference)
                                print str(k) + " with Name =" + str(dictParameter[k].name)
                                print dictParameter[k]
                            
                    else:
                        objectTree.addFromString(strNames, dictParameter[k])
            
            if pedantic:
                print objectTree.get_all()
            
            return True
        
        except IndexError:
            # An error can occur if the FMU has not yet been loaded
            print "FMU not yet loaded..."
            return False
    
    def get_tree_by_type(self, Type):
        """
        This method given a string that describes a given type of tree, it returns that tree
        """
        if Type == fmu_util_strings.PARAMETER_STRING:
            return self.treeParameters
        if Type == fmu_util_strings.VARIABLE_STRING:
            return self.treeVariables
        if Type == fmu_util_strings.INPUT_STRING:
            return self.treeInputs
        if Type == fmu_util_strings.OUTPUT_STRING:
            return self.treeOutputs
        else:
            print "No Match between the type passes and the available trees"
            return None
    
    def get_variables(self):
        """
        Return the list of state variables contained by the FMU that have been selected
        """
        return self.variables
    
    def get_variable_info_numeric(self, variableInfo):
        """
        Given a variableInfo object that may be related either to a parameter, a state variable, an input or a output
        This function returns the values and details associated to it.
        """
        
        try:
            # Take the data type associated to the variable
            Type  = self.fmu.get_variable_data_type(variableInfo.name)
            
            # According to the data type read, select one of these methods to get the information
            if Type == pyfmi.fmi.FMI_REAL:
                value = self.fmu.get_real( variableInfo.value_reference )
            elif Type == pyfmi.fmi.FMI_INTEGER:
                value = self.fmu.get_integer( variableInfo.value_reference )
            elif Type == pyfmi.fmi.FMI_BOOLEAN:
                value = self.fmu.get_boolean( variableInfo.value_reference )
            elif Type == pyfmi.fmi.FMI_ENUMERATION:
                value = self.fmu.get_int( variableInfo.value_reference )
            elif Type == pyfmi.fmi.FMI_STRING:
                value = self.fmu.get_string( variableInfo.value_reference )
            else:
                print "OnSelChanged::FMU-EXCEPTION :: The type is not known"
                value = 0.0
 
            # TODO: check the min and max value if the variables are not real or integers
            Min   = self.fmu.get_variable_min(variableInfo.name)
            Max   = self.fmu.get_variable_max(variableInfo.name)
                
            try:
                start = self.fmu.get_variable_start(variableInfo.name)
            except pyfmi.fmi.FMUException:
                print "Default start value defined as 0.0"
                start = 0.0
            
            return (type, value, start, Min, Max)
        
        except pyfmi.fmi.FMUException:
                # if the real value is not present for this parameter/variable
                print "OnSelChanged::FMU-EXCEPTION :: No real value to read for this variable"
                return (None, None, None, None, None)
    
    def get_variable_info(self, variableInfo):
        """
        Given a variableInfo object that may be related either to a parameter, a state variable, an input or a output
        This function returns the values and details associated to it.
        """
        
        try:
            # Take the data type associated to the variable
            Type  = self.fmu.get_variable_data_type(variableInfo.name)
            
            # According to the data type read, select one of these methods to get the information
            if Type == pyfmi.fmi.FMI_REAL:
                value = self.fmu.get_real( variableInfo.value_reference )
                strType = "Real"
            elif Type == pyfmi.fmi.FMI_INTEGER:
                value = self.fmu.get_integer( variableInfo.value_reference )
                strType = "Integer"
            elif Type == pyfmi.fmi.FMI_BOOLEAN:
                value = self.fmu.get_boolean( variableInfo.value_reference )
                strType = "Boolean"
            elif Type == pyfmi.fmi.FMI_ENUMERATION:
                value = self.fmu.get_int( variableInfo.value_reference )
                strType = "Enum"
            elif Type == pyfmi.fmi.FMI_STRING:
                value = self.fmu.get_string( variableInfo.value_reference )
                strType = "String"
            else:
                print "OnSelChanged::FMU-EXCEPTION :: The type is not known"
                value = [""]
                strType = "Unknown"
 
            # TODO: check the min and max value if the variables are not real or integers
            Min   = self.fmu.get_variable_min(variableInfo.name)
            Max   = self.fmu.get_variable_max(variableInfo.name)
                
            try:
                start = str(self.fmu.get_variable_start(variableInfo.name))
                fixed = self.fmu.get_variable_fixed(variableInfo.name)
                start = start+" (fixed ="+str(fixed)+")"
            except pyfmi.fmi.FMUException:
                start = ""
                
            strVal = str(value[0])
            strMin = str(Min)
            strMax = str(Max)
            if min < -1.0e+20:
                strMin = "-Inf"
            if max > 1.0e+20:
                strMax = "+Inf"
            
            return (strType, strVal, start, strMin, strMax)
        
        except pyfmi.fmi.FMUException:
                # if the real value is not present for this parameter/variable
                print "OnSelChanged::FMU-EXCEPTION :: No real value to read for this variable"
                return ("", "", "", "", "")
    
    def get_variable_names(self):
        """
        This method returns a list of names for each state variables observed
        """
        varNames = []
        for var in self.variables:
            # EstimationVariable
            varNames.append(var.name)
        return varNames
    
    def get_variable_object(self, name = None):
        """
        This method returns a PyFMI variable given its name
        """
        if name != None and name != "":
            if self.fmu != None:
                try:
                    return self.fmu.get_model_variables()[name]
                except Exception:
                    print "The variable or parameter: "+str(name)+" is not available in the list:"
                    print self.fmu.get_model_variables().keys()
                    return None
            else:
                print "The FMU model has not yet been set. Impossible return the variable "+str(name)
                return None
        else:
            print "Impossible to look for the name because it is None or empty"
            return None
    
    def get_variables_tree(self):
        """
        This method returns the tree associated to the state variables of the model
        """
        return self.treeVariables
    
    def initialize_simulator(self, startTime = None):
        """
        This method performs a very short simulation to initialize the model.
        The next times the model will be simulated without the initialization phase.
        By default the simulation is performed at the initial time of the input data series, but the
        user can specify an other point.
        """
        # TODO: Done
        # Load the inputs and check if any problem. If any exits.
        # Align inputs while loading.
        if not self.load_input(align = True):
            return False
        
        # Load the outputs and check if any problems. If any exits.
        if not self.load_outputs():
            return False
        
        # Take the time series: the first because now they are all the same (thanks to alignment)
        time = self.inputs[0].get_data_series().index
        
        # Define the initial time for the initialization
        if startTime == None:
            # Start time not specified, start from the beginning
            index = 0
        else:
            
            # Check that the type of start time is of type datetime
            if not isinstance(startTime, datetime.datetime):
                raise TypeError("The parameter startTime has to be of datetime.datetime type")
                
            # Start time specified, start from the closest point
            if startTime >= time[0] and startTime <= time[-1]:
                index = 0
                for t in time:
                    if t < startTime:
                        index += 1
                    else:
                        break
            else:
                index = 0
                raise IndexError("The value selected as initialization start time is outside the time frame")
                
        # Once the index is know it can be used to define the start_time
        start_time = time[index]
        
        # Take all the data series
        Ninputs = len(self.inputs)
        start_input = numpy.zeros((1, Ninputs))
        start_input_1 = numpy.zeros((1, Ninputs))
        start_input_2 = numpy.zeros((1, Ninputs))
        i = 0
        if index == 0:
            for inp in self.inputs:
                dataInput = numpy.matrix(inp.get_data_series().values).reshape(-1,1)
                start_input[0, i] = dataInput[index,0]
                i += 1
        else:
            for inp in self.inputs:
                dataInput = numpy.matrix(inp.get_data_series().values).reshape(-1,1)
                start_input_1[0, i] = dataInput[index-1,0]
                start_input_2[0, i] = dataInput[index,0]
                
                # Linear interpolation between the two values
                dt0 = (time[index] - start_time).total_seconds()
                dT1 = (start_time  - time[index-1]).total_seconds()
                DT  = (time[index] - time[index-1]).total_seconds()
                
                # Perform the interpolation
                start_input[0, i] = (dt0*start_input_1[0, i] + dT1*start_input_2[0, i])/DT
                
                i += 1
               
        # Initialize the model for the simulation
        self.opts["initialize"] = True
        
        try:
            # Simulate from the initial time to initial time + epsilon
            # thus we have 2 points
            
            # Create the input objects for the simulation that initializes
            Input = numpy.hstack((start_input, start_input))
            Input = Input.reshape(2,-1)
            
            time = pd.DatetimeIndex([start_time, start_time])
            
            # Run the simulation, remember that
            # time has to be a dateteTimeIndex and Input has to be a numpy.matrix
            self.simulate(time = time, Input = Input)
            self.opts["initialize"] = False
            
            # Initialize the selected variables and parameters to the values indicated 
            # Done after very small simulation because there can be some internal parameters that defines
            # the initial value and may override the initialization with the indicated values
            for v in self.variables:
                v.modify_initial_value_in_fmu(self.fmu)
            for p in self.parameters:
                p.modify_initial_value_in_fmu(self.fmu)
            
            return True
        
        except ValueError:
            print "First simulation for initialize the model failed"
            return False
    
    def is_parameter_present(self, obj):
        """
        This method returns true is the parameter is contained in the list of parameters of the model
        """
        val_ref = obj.value_reference
        for p in self.parameters:
            if p.value_reference == val_ref:
                # there is already a parameter in the list with the same value_reference
                print "There is already a parameter in the list with the same value reference: "+str(val_ref)
                return True
        return False
    
    def is_variable_present(self, obj):
        """
        This method returns true is the variable is contained in the list of variable of the model
        """
        val_ref = obj.value_reference
        for v in self.variables:
            if v.value_reference == val_ref:
                # there is already a variable in the list with the same value_reference
                print "There is already a variable in the list with the same value reference: "+str(val_ref)
                return True
        return False
    
    def load_input(self, align = True):
        """
        This method loads all the input data series. It returns a boolean if the import was successful.
        """
        # TODO: Done
        # Get all the data series from the CSV files (for every input of the model)
        LoadedInputs = True
        for inp in self.inputs:
            LoadedInputs = LoadedInputs and inp.read_data_series()
        
        if not LoadedInputs:
            print "An error occurred while loading the inputs"
        else:
            # A check on the input data series should be performed: Are the initial times, final times and number of point
            # aligned? If not perform an interpolation to align them is done. The boolean flag align deals with this.
            print "Check the input data series..."
            if not self.check_input_data(align):
                print "Re-Check the input data series..."
                return self.check_input_data(align)
            
        return LoadedInputs
    
    def load_outputs(self):
        """
        This method loads all the output data series. It returns a boolean if the import was successful
        """
        # TODO: Done
        # Get all the data series from the CSV files (for every input of the model)
        LoadedOutputs = True
        for o in self.outputs:
            if o.is_measured_output():
                LoadedOutputs = LoadedOutputs and o.read_data_series()
        
        if not LoadedOutputs:
            print "An error occurred while loading the outputs"
        
        return LoadedOutputs
    
    def re_init(self, fmuFile, result_handler = None, solver = None, atol = 1e-6, rtol = 1e-4, setTrees = False, verbose=None):
        """
        This function reinitializes the FMU associated to the model
        """
        print "Previous FMU was: ",self.fmu
        print "Reinitialized model with: ",fmuFile
        if self.fmu != None:
            self.fmu = None
        self.__init__(fmuFile, result_handler, solver, atol, rtol, setTrees, verbose)
    
    def remove_parameter(self, obj):
        """
        This method removes one object to the list of parameters. This list contains only the parameters that 
        will be modified during the further analysis
        """
        try:
            index = self.parameters.index(obj)
            self.parameters.pop(index)
            return True
        except ValueError:
            # the object cannot be removed because it is not present
            return False
        
    def remove_parameters(self):
        """
        This method removes all the objects from the list of parameters.
        """
        self.parameters = []
    
    def remove_variable(self, obj):
        """
        This method remove one object to the list of variables. This list contains only the parameters that 
        will be modified during the further analysis
        """
        try:
            index = self.variables.index(obj)
            self.variables.pop(index)
            return True
        except ValueError:
            # the object cannot be removed because it is not present
            return False
    
    def remove_variables(self):
        """
        This method removes all the objects from the list of parameters.
        """
        self.variables = []
    
    def unload_fmu(self):
        """
        This method unload the FMU model and it deallocate the resources associated to it.
        This is necessary is an other FMU model needs to be loaded.
        """
        del(self.fmu)
    
    def __set_fmu__(self, fmuFile, result_handler, solver, atol, rtol, verbose):
        """
        This method associate an FMU to a model, if not yet assigned
        """
        if self.fmu == None:
            
            #TODO:
            # See what can be done in catching the exception/propagating it
            self.fmu = pyfmi.load_fmu(fmuFile)
                
            # Get the options for the simulation
            self.opts = self.fmu.simulate_options()
            
            # Define the simulation options
            self.set_simulation_options(result_handler, solver, atol, rtol, verbose)
            
            # Define the standard value for the result file
            self.set_result_file(None)
            
            # set the number of states
            self.N_STATES = len(self.get_state())
            
            # get the value references of the state variables
            self.stateValueReferences = self.fmu.get_state_value_references()
            
            # Properties of the FMU
            self.name = str(self.fmu.get_name())
            self.author = str(self.fmu.get_author())
            self.description = str(self.fmu.get_description())
            self.type = str(self.fmu.__class__.__name__)
            self.version = str(self.fmu.version)
            self.guid = str(self.fmu.get_guid())
            self.tool = str(self.fmu.get_generation_tool())
            [Ncont, Nevt] = self.fmu.get_ode_sizes()
            self.numStates = "( "+str(Ncont)+" , "+str(Nevt)+" )"
            
            # prepare the list of inputs and outputs
            self.__set_inputs__()
            self.__set_outputs__()
            
        else:
            print "WARNING: The fmu has already been assigned to this model! Check your code!"
        
    def __set_inputs_tree__(self):
        """
        This method updates the inputs tree structure
        """
        if not self.__set_generalized_tree__(None, 0):
            print "Problems while creating the inputs tree"
            self.treeInputs = Tree(fmu_util_strings.INPUT_STRING)
            
    def __set_generalized_tree__(self, variability, causality, onlyStates = False, pedantic = False):
        """
        This method populates 
        """
        if variability == 1 and causality == None:
            # parameters
            done = self.get_tree(self.treeParameters, variability, causality, onlyStates, pedantic)
        if variability == 3 and causality == None:
            # state variables
            done = self.get_tree(self.treeVariables, variability, causality, onlyStates, pedantic)
        if variability == None and causality == 1:
            # outputs
            done = self.get_tree(self.treeOutputs, variability, causality, onlyStates, pedantic)
        if variability == None and causality == 0:
            # inputs
            done = self.get_tree(self.treeInputs, variability, causality, onlyStates, pedantic)
            
        return done
    
    def __set_inputs__(self):
        """
        This function sets the input variables of a model
        """
        self.__set_in_out_var__(None, 0)
    
    def __set_in_out_var__(self, variability, causality):
        """
        "Input"
            causality = 0
            variability = None
        "Outputs"
            causality = 1
            variability = None
        """
        # Take the variable of the FMU that have the specified variability and causality
        # the result is a dictionary which has as key the name of the variable with the dot notation
        # and as element a class of type << pyfmi.fmi.ScalarVariable >>
        # Alias variable removed for clarity.
        dictVariables = self.fmu.get_model_variables(include_alias = False, variability = variability, causality = causality)
            
        for k in dictVariables.keys():
            # The object attached to each leaf of the tree is << dictParameter[k] >>
            # which is of type << pyfmi.fmi.ScalarVariable >>
            
            var = InOutVar()
            var.set_object(dictVariables[k])
            
            if variability == None and causality ==0:
                # input
                self.inputs.append(var)
            if variability == None and causality ==1:
                # output
                self.outputs.append(var)

    def __set_outputs__(self):
        """
        This function sets the output variables of a model
        """
        self.__set_in_out_var__(None, 1)
    
    def __set_outputs_tree__(self):
        """
        This method updates the outputs tree structure
        """
        if not self.__set_generalized_tree__(None, 1):
            print "Problems while creating the outputs tree"
            self.treeOutputs = Tree(fmu_util_strings.OUTPUT_STRING)
    
    def __set_parameters_tree__(self):
        """
        This method updates the parameters tree structure
        """
        if not self.__set_generalized_tree__(1, None):
            print "Problems while creating the parameters tree"
            self.treeParameters = Tree(fmu_util_strings.PARAMETER_STRING)
    
    def set_result_file(self, fileName):
        """
        This method modifies the name of the file that stores the simulation results
        """
        if fileName!= None:
            self.opts["result_file_name"] = fileName
        else:
            self.opts["result_file_name"] = ""
    
    def set_simulation_options(self, result_handler, solver, atol, rtol, verbose):
        """
        This method set the options of the simulator
        """
        # The result handling can be one of
        # "file", "memory", "custom" (in the latter case a result handler has to be specified)
        # By default they are on memory
        if result_handler != None and result_handler in fmu_util_strings.SIMULATION_OPTION_RESHANDLING_LIST:
            self.opts[fmu_util_strings.SIMULATION_OPTION_RESHANDLING_STRING] = result_handler
        else:
            self.opts[fmu_util_strings.SIMULATION_OPTION_RESHANDLING_STRING] = fmu_util_strings.RESULTS_ON_MEMORY_STRING
        
        
        # Set solver verbose level
        if verbose != None and  verbose in fmu_util_strings.SOLVER_VERBOSITY_LEVELS:
            for s in fmu_util_strings.SOLVER_NAMES_OPTIONS:   
                self.opts[s][fmu_util_strings.SOLVER_OPTION_VERBOSITY_STRING] = verbose
        else:
            for s in fmu_util_strings.SOLVER_NAMES_OPTIONS:   
                self.opts[s][fmu_util_strings.SOLVER_OPTION_VERBOSITY_STRING] = fmu_util_strings.SOLVER_VERBOSITY_QUIET
        
              
        # Set the absolute and relative tolerance of each solver, otherwise the default value
        # is left
        if atol != None and atol > 0 and numpy.isreal(atol):
            for s in fmu_util_strings.SOLVER_NAMES_OPTIONS:   
                self.opts[s][fmu_util_strings.SOLVER_OPTION_ATOL_STRING] = atol
        if rtol != None and rtol > 0 and numpy.isreal(rtol):
            for s in fmu_util_strings.SOLVER_NAMES_OPTIONS:   
                self.opts[s][fmu_util_strings.SOLVER_OPTION_RTOL_STRING] = rtol
        
    def set_state(self, stateVector):
        """
        This method sets the entire state variables vector of the model
        """
        self.fmu._set_continuous_states(stateVector)
    
    def set_real(self, var, value):
        """
        Set a real variable in the FMU model, given the PyFmi variable description
        """
        self.fmu.set_real(var.value_reference, value)
        return
    
    def set_state_selected(self, vector):
        """
        This method sets the state variable contained in the list self.variables
        to the values passed by the vector
        """
        if len(vector) == len(self.variables):
            # The vector have compatible dimensions
            i = 0
            for v in self.variables:
                self.fmu.set_real(v.value_reference, vector[i])
                i += 1
            return True
        else:
            # the vectors are not compatibles
            return False
    
    def set_parameters_selected(self, vector):
        """
        This method sets the parameters contained in the list self.parameters
        to the values passed by the vector
        """
        if len(vector) == len(self.parameters):
            # The vector have compatible dimensions
            i = 0
            for p in self.parameters:
                self.fmu.set_real(p.value_reference, vector[i])
                i += 1
            return True
        else:
            # the vectors are not compatibles
            return False
    
    def __set_trees__(self):
        """
        This method sets the trees associated to all parameters, variables, inbputs and outputs
        """
        self.__set_inputs_tree__()
        self.__set_outputs_tree__()
        self.__set_parameters_tree__()
        self.__set_variables_tree__()
        pass
    
    def __set_variables_tree__(self):
        """
        This method updates the variables tree structure
        """
        if not self.__set_generalized_tree__(3, None, True):
            print "Problems while creating the variables tree"
            self.treeVariables = Tree(fmu_util_strings.VARIABLE_STRING)
    
    def simulate(self, start_time = None, final_time = None, time = pd.DatetimeIndex([]), Input = None, complete_res = False):
        """
        This method simulates the model from the start_time to the final_time, using a given set of simulation
        options. Since it may happen that a simulation fails without apparent reason (!!), it is better to 
        simulate again the model if an error occurs. After N_TRIES it stops.
        input = [[u1(T0), u2(T0), ...,uM(T0)],
                 [u1(T1), u2(T1), ...,uM(T1)],
                 ...
                 [u1(Tend), u2(Tend), ...,uM(Tend)]]
        """
        # TODO
        
        # Number of input variables needed by the model
        Ninputs = len(self.inputs)
        
        # Check if the parameter time has been provided
        if len(time) == 0:
            # Take the time series: the first because now they are all the same
            for inp in self.inputs:
                time = inp.get_data_series().index
                break
        else:
            # Check that the type of the time vector is of type pd.DatetimeIndex
            if not isinstance(time, pd.DatetimeIndex):
                raise TypeError("The parameter time has to be a vector of type pd.DatetimeIndex")
            
        # Define initial start time in seconds
        if start_time == None:
            start_time = time[0]
        else:
            # Check that the type of start time is of type datetime
            if not isinstance(start_time, datetime.datetime):
                raise TypeError("The parameter start_time is of type %s, it has to be of datetime.datetime type." % (str(start_time)))
            # Check if the start time is within the range
            if not (start_time >= time[0] and start_time <= time[-1]):
                raise IndexError("The value selected as initialization start time is outside the time frame")
            
        start_time_sec = (start_time - time[0]).total_seconds()
        
        # Define the final time in seconds
        if final_time == None:
            final_time = time[-1]
        else:
            # Check that the type of start time is of type datetime
            if not isinstance(final_time, datetime.datetime):
                raise TypeError("The parameter final_time is of type %s, it has to be of datetime.datetime type." % (str(start_time)))
            # Check if the final time is within the range
            if not (final_time >= time[0] and final_time <= time[-1]):
                raise IndexError("The value selected as initialization start time is outside the time frame")
            # Check that the final time is after the start time
            if not (final_time >= start_time):
                raise IndexError("The final_time %s has to be after the start time %s." % \
                                 (str(final_time), str(start_time)))
        final_time_sec = (final_time - time[0]).total_seconds()
            
        # Transforms to seconds with respect to the first element
        Npoints = len(time)
        time_sec = numpy.zeros((Npoints,1))
        for i in range(Npoints):
            time_sec[i,0] = (time[i] - time[0]).total_seconds()
        
        # Convert to numpy matrix in case it will be stacked in a matrix
        time_sec = numpy.matrix(time_sec)
        
        # Reshape to be consistent
        time_sec  = time_sec.reshape(-1, 1)
        
        if Input == None:
            # Take all the data series
            inputMatrix = numpy.matrix(numpy.zeros((Npoints, Ninputs)))
            
            i = 0
            for inp in self.inputs:
                dataInput = numpy.matrix(inp.get_data_series().values).reshape(-1,1)
                inputMatrix[:, i] = dataInput[:,:]
                i += 1
            # Define the input trajectory
            V = numpy.hstack((time_sec, inputMatrix))
            
        else:
            # Reshape to be consistent
            Input = Input.reshape(-1, Ninputs)
            # Define the input trajectory
            V = numpy.hstack((time_sec, Input))
        
        # The input trajectory must be an array, otherwise pyfmi does not work
        u_traj  = numpy.array(V)
        
        # Create input object
        names = self.get_input_names()
        input_object = (names, u_traj)
        
        # TODO
        # Associate functions rather than a matrix that contains all the values
        # input_object = (names, self.get_input_readers)
        
        # Start the simulation
        simulated = False
        i = 0
        while not simulated and i < self.SIMULATION_TRIES:
            try:
                res = self.fmu.simulate(start_time = start_time_sec, input = input_object, final_time = final_time_sec, options = self.opts)
                simulated = True
            except ValueError:
                print "Simulation of the model failed, try again"
                i += 1
            except Exception, e:
                print str(e)
                print "Simulation of the model failed between {0} and {1}, try again".format(start_time, final_time)
                i += 1 
        
        # Check if the simulation has been done, if not through an exception
        if not simulated:
            print self.fmu.get_log()
            raise Exception
        
        # Obtain the results
        # TIME in seconds has to be converted to datetime
        # and it has to maintain the same offset specified by the input time series in t[0]
        offset = time[0] - pd.to_datetime(res[fmu_util_strings.TIME_STRING][0])
        t     = pd.to_datetime(res[fmu_util_strings.TIME_STRING], unit="s") + offset
        
        # Get the results, either all or just the selected ones
        if complete_res == False:
            # OUTPUTS
            output_names = self.get_output_names()
            results = {}
            for name in output_names:
                results[name] = res[name]
            # STATES OBSERVED
            var_names = self.get_variable_names()
            for name in var_names:
                results[name] = res[name]
            # PARAMETERS
            par_names = self.get_parameter_names()
            for name in par_names:
                results[name] = res[name]
            
            # THE OVERALL STATE
            results["__ALL_STATE__"]=self.get_state()
            results["__OBS_STATE__"]=self.get_state_observed_values()
            results["__PARAMS__"]=self.get_parameter_values()
            results["__OUTPUTS__"]=self.get_measured_outputs_values()
            results["__ALL_OUTPUTS__"]=self.get_outputs_values()
            
        else:
            # All the results are given back
            results = res
            
        # Return the results
        return (t, results)
    
    def __str__(self):
        """
        Built-in function to print description of the object
        """
        string = "\nFMU based Model:"
        string += "\n-File: "+str(self.fmuFile)
        string += "\n-Name: "+self.name
        string += "\n-Author: "+self.author
        string += "\n-Description: "+ self.description
        string += "\n-Type: "+self.type
        string += "\n-Version: "+self.version
        string += "\n-GUID: "+self.guid
        string += "\n-Tool: "+self.tool
        string += "\n-NumStates: "+self.numStates+"\n"
        return string
    
    def toggle_parameter(self, obj):
        """
        If the parameter is already present it is removed, otherwise it is added
        """
        if self.is_parameter_present(obj):
            self.remove_parameter(obj)
        else:
            self.add_parameter(obj)
    
    def toggle_variable(self, obj):
        """
        If the variable is already present it is removed, otherwise it is added
        """
        if self.is_variable_present(obj):
            self.remove_variable(obj)
        else:
            self.add_variable(obj)