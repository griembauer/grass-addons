#!/usr/bin/env python
#
############################################################################
#
# MODULE:		FIDIMO Fish Dispersal Model for River Networks for GRASS 7
#
# AUTHOR(S):		Johannes Radinger
#				
# VERSION:		V0.1 Beta
#
# DATE:			2013-04-11
#
#############################################################################
#%Module
#% description: Calculating fish dispersal in a river network from source populations with species specific dispersal parameters
#% keywords: Fish Dispersal Model
#%End
#%option
#% key: river
#% type: string
#% gisprompt: old,cell,raster
#% description: River network (raster-file, e.g. output from r.stream.extract or fidimo.river)
#% required: no
#% guisection: Stream parameters
#%end
#%option
#% key: coors
#% type: string
#% required: no
#% multiple: no
#% key_desc: x,y
#% description: River networks' outlet coordinates: E,N
#% guisection: Stream parameters
#%End
#%option
#% key: barriers
#% type: string
#% gisprompt:old,vector,vector
#% description: Barrier point file
#% required: no
#% guisection: Stream parameters
#%end
#%option
#% key: passability_col
#% type: string
#% required: no
#% multiple: no
#% key_desc: name
#% description: Column name indicating passability value (0-1) of barrier
#% guisection: Stream parameters
#%End
#%option
#% key: n_source
#% type: string
#% key_desc: number[%]
#% description: Either: Number of random cells with source populations
#% required: no
#% guisection: Source populations
#%end
#%option
#% key: source_populations
#% type: string
#% gisprompt: old,cell,raster
#% description: Or: Source population raster, e.g output from SDM
#% required: no
#% guisection: Source populations
#%end
#%Option
#% key: species
#% type: string
#% required: no
#% multiple: no
#% options:Custom species,Catostomus commersoni,Moxostoma duquesnii,Moxostoma erythrurum,Ambloplites rupestris,Lepomis auritus,Lepomis cyanellus,Lepomis macrochirus,Lepomis megalotis,Micropterus dolomieui,Micropterus punctulatus,Micropterus salmoides,Pomoxis annularis,Cottus bairdii,Cottus gobio,Abramis brama,Barbus barbus,Cyprinus carpio carpio,Gobio gobio,Leuciscus idus,Rutilus rutilus,Squalius cephalus,Tinca tinca,Esox lucius,Fundulus heteroclitus heteroclitus,Ameiurus natalis,Ictalurus punctatus,Morone americana,Etheostoma flabellare,Etheostoma nigrum,Perca fluviatilis,Percina nigrofasciata,Sander lucioperca,Oncorhynchus mykiss, Oncorhynchus gilae,Salmo salar,Salmo trutta fario,Salvelinus fontinalis,Salvelinus malma malma,Thymallus thymallus,Aplodinotus grunniens,Salmo trutta,Gobio gobio,Rutilus rutilus
#% description: Select fish species
#% guisection: Dispersal parameters
#%End
#%Option
#% key: L
#% type: integer
#% required: no
#% multiple: no
#% description: Fish Length (If no species is given)
#% guisection: Dispersal parameters
#% options: 39-810
#%End
#%Option
#% key: AR
#% type: double
#% required: no
#% multiple: no
#% description: Aspect Ratio of Caudal Fin (If no species is given) (valid range 0.51 - 2.29)
#% guisection: Dispersal parameters
#%End
#%Option
#% key: T
#% type: integer
#% required: no
#% multiple: no
#% description: Time interval for model step in days
#% guisection: Dispersal parameters
#% options: 1-3285
#% answer: 30
#%End
#%option
#% key: p
#% type: double
#% required: no
#% multiple: no
#% description: Share of the stationary component (valid range 0 - 1)
#% answer:0.67 
#% guisection: Dispersal parameters
#%End
#%Flag
#% key: b
#% description: Don't keep basic vector maps (source_points, barriers)
#%end
#%Flag
#% key: a
#% description: Keep all temporal vector and raster maps
#%end
#%Option
#% key: truncation
#% type: string
#% required: no
#% multiple: no
#% options: 0.9,0.95,0.99,0.995,0.999,0.99999,0.999999999,inf
#% description: kernel truncation criterion (precision)
#% answer: 0.99
#% guisection: Optional
#%End
#%Option
#% key: output
#% type: string
#% required: no
#% multiple: no
#% key_desc: name
#% description: Base name for output raster
#% guisection: Output
#% answer: fidimo_out
#%end
#%Option
#% key: statistical_interval
#% type: string
#% required: no
#% multiple: no
#% key_desc: name
#% description: Statistical Intervals
#% guisection: Output
#% options:no,Confidence Interval,Prediction Interval
#% answer:no
#%end


# import required base modules
import sys
import os
import atexit
import time
import sqlite3
import math #for function sqrt()
import csv

# import required grass modules
import grass.script as grass
import grass.script.setup as gsetup
import grass.script.array as garray

#import random

# import required numpy/scipy modules
import numpy
from scipy import stats
from scipy import optimize



tmp_map_rast = None
tmp_map_vect = None

def cleanup():
	if (tmp_map_rast or tmp_map_vect) and not flags['a']:
		grass.run_command("g.remove", 
				rast = [f + str(os.getpid()) for f in tmp_map_rast],
				vect = [f + str(os.getpid()) for f in tmp_map_vect],
				quiet = True)




def main():
	
	############ DEFINITION CLEANUP TEMPORARY FILES ##############
	#global variables for cleanup
	global tmp_map_rast
	global tmp_map_vect

	tmp_map_rast = ['density_final_','density_final_corrected_','density_from_point_tmp_', 'density_from_point_unmasked_tmp_', 'distance_from_point_tmp_', 'distance_raster_tmp_', 'division_overlay_tmp_', 'downstream_drain_tmp_', 'flow_direction_tmp_', 'lower_distance_tmp_', 'rel_upstream_shreve_tmp_', 'river_raster_cat_tmp_', 'river_raster_tmp_', 'shreve_tmp_', 'source_populations_scalar_', 'strahler_tmp_', 'stream_rwatershed_tmp_', 'upper_distance_tmp_', 'upstream_part_tmp_', 'upstream_shreve_tmp_']


	tmp_map_vect = ['river_points_tmp_', 'river_vector_tmp_', 'river_vector_nocat_tmp_','source_points_']


	if options['barriers']:
		tmp_map_rast = tmp_map_rast + ['downstream_barrier_density_tmp_','distance_barrier_tmp_', 'distance_downstream_barrier_tmp_', 'lower_distance_barrier_tmp_', 'upper_distance_barrier_tmp_', 'upstream_barrier_tmp_',  'upstream_barrier_density_tmp_']
		tmp_map_vect = tmp_map_vect + ["barriers_",'barriers_tmp_']



	############ PARAMETER INPUT ##############
	#Stream parameters input
	river = options['river']
	coors = options['coors']

	# Barrier input
	if options['barriers']:
		input_barriers = options['barriers'].split('@')[0]
		# check if barrier file exists in current mapset (Problem when file in other mapset!!!!)
		if not grass.find_file(name = input_barriers, element = 'vector')['file']:
			grass.fatal(_("Barriers map not found in current mapset"))		
		# check if passability_col is provided and existing
		if not options['passability_col']:
			grass.fatal(_("Please provide column name that holds the barriers' passability values ('passability_col')"))
		if not options['passability_col'] in grass.read_command("db.columns", table=input_barriers).split('\n'):
			grass.fatal(_("Please provide correct column name that holds the barriers' passability values ('passability_col')"))
		passability_col = options['passability_col']
		


	#Source population input
	if (options['source_populations'] and options['n_source']) or (str(options['source_populations']) == '' and str(options['n_source']) == ''):
		grass.fatal(_("Provide either fixed or random source population"))

	n_source = options['n_source'] #number of random source points
	source_populations = options['source_populations']
	

	# multiplication value as workaround for very small FLOAT values
	#imporatant for transformation of source population raster into point vector
	scalar = 10**200

	# Statistical interval
	if (str(options['statistical_interval']) == 'Prediction Interval'):
		interval = "prediction"
	else:
		interval = "confidence"
	

	#Output
	output_fidimo = options['output']
	if (grass.find_file(name = output_fidimo+"_"+"fit", element = 'cell')['file'] and not grass.overwrite()):
		grass.fatal(_("Output file exists already, either change output name or set overwrite-flag"))




	
	############ FISHMOVE ##############
	
	# import required rpy2 module
	import rpy2.robjects as robjects
	from rpy2.robjects.packages import importr
	fm = importr('fishmove')

	#Dispersal parameter input
	if str(options['species']!="Custom species") and (options['L'] or options['AR']):
		grass.message(_("Species settings will be overwritten with L and AR"))
	species = str(options['species'])
	if options['L']:
		L = float(options['L'])
	if options['AR']:
		AR = float(options['AR'])
	T = float(options['T'])
	# Setting Stream order to a vector of 1:9 and calculate fishmove for all streamorders at once
	SO = robjects.IntVector((1,2,3,4,5,6,7,8,9))
	m = 0 # m-parameter in dispersal function
	if (float(options['p']) >= 0 and float(options['p']) < 1):
		p =float(options['p'])
	else:
		grass.fatal(_("Valid range for p: 0 - 1"))


	##### Calculating 'fishmove' depending on species or L & AR
	if species == "Custom species":
		fishmove = fm.fishmove(L=L,AR=AR,SO=SO,T=T,interval=interval)
	else:
		fishmove = fm.fishmove(species=species,SO=SO,T=T,interval=interval)

	# using only part of fishmove results (only regression coeffients)
	fishmove = fishmove[1]
	nrun = ['fit','lwr','upr']




	
	############ REGION, DB-CONNECTION ##############
	#Setting region to extent of input River
	grass.run_command("g.region",
					  flags = "a",
					  rast = river,
					  overwrite = True,
					  save = "region_Fidimo")

	#Getting resultion, res=cellsize
	res = int(grass.read_command("g.region",
					  flags = "m").strip().split('\n')[4].split('=')[1])


	#database-connection
	env = grass.gisenv()
	gisdbase = env['GISDBASE']
	location = env['LOCATION_NAME']
	mapset = env['MAPSET']
	grass.run_command("db.connect",
					  driver = "sqlite",
					  database = "$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite.db")	 
	database = sqlite3.connect(os.path.join(gisdbase, location, mapset, 'sqlite.db'))
	db = database.cursor()
	
	#############################################
	############################################# 


 
	################ Preparation River Raster (Distance-Raster) ################
	

	# Populate input-river (raster) with value of resolution
	# *1.0 to get float raster instead of integer
	grass.mapcalc("$river_raster = if($river,$res*1.0)",
					  river_raster = "river_raster_tmp_%d" % os.getpid(),
					  river = river,
					  res = res)


	# Converting river_raster to river_vector 
	grass.run_command("r.to.vect",
					  overwrite = True,
					  input="river_raster_tmp_%d" % os.getpid(),
					  output="river_vector_tmp_%d" % os.getpid(),
					  type="line")
	
	# Converting river_raster to river_point
	grass.run_command("r.to.vect",
					  overwrite = True,
					  input="river_raster_tmp_%d" % os.getpid(),
					  output="river_points_tmp_%d" % os.getpid(),
					  type="point")	



	#Prepare Barriers/Snap barriers to river_vector
	if options['barriers']:
		grass.run_command("g.copy", 
						vect = input_barriers + "," + "barriers_tmp_%d" % os.getpid())

		grass.run_command("v.db.addcolumn",
						  map ="barriers_tmp_%d" % os.getpid(),
						  columns="new_X DOUBLE, new_Y DOUBLE")					
		grass.run_command("v.distance",
						  overwrite = True,
						  _from="barriers_tmp_%d" % os.getpid(),
						  to="river_vector_tmp_%d" % os.getpid(),
						  upload="to_x,to_y",
						  column="new_X,new_Y")
		grass.run_command("v.in.db",
						  overwrite = True,
						  table="barriers_tmp_%d" % os.getpid(),
						  x="new_X",
						  y="new_Y",
						  key="cat",
						  output="barriers_%d" % os.getpid())
		grass.run_command("v.db.addcolumn",
						  map ="barriers_%d" % os.getpid(),
						  columns="dist DOUBLE") 
			
		#Breaking river_vector at position of barriers to get segments
		for new_X,new_Y in db.execute('SELECT new_X, new_Y FROM barriers_%d'% os.getpid()):
			barrier_coors = str(new_X)+","+str(new_Y)
		
			grass.run_command("v.edit",
						  map="river_vector_tmp_%d" % os.getpid(),
						  tool="break",
						  thresh="1,0,0",
						  coords=barrier_coors)


	#Getting category values (ASC) for river_network segments
	grass.run_command("v.category",
					overwrite=True,
					input="river_vector_tmp_%d" % os.getpid(),
					option="del",
					output="river_vector_nocat_tmp_%d" % os.getpid())
	grass.run_command("v.category",
					overwrite=True,
					input="river_vector_nocat_tmp_%d" % os.getpid(),
					option="add",
					output="river_vector_tmp_%d" % os.getpid()) 



	#Check if outflow coors are on river
	# For GRASS7 snap coors to river. Check r.stream.snap - add on
	# !!!!!!


	#Calculation of distance from outflow and flow direction for total river
	grass.run_command("r.cost",
					  flags = 'n',
					  overwrite = True,
					  input = "river_raster_tmp_%d" % os.getpid(),
					  output = "distance_raster_tmp_%d" % os.getpid(),
					  start_coordinates = coors)

	largest_cost_value = grass.raster_info("distance_raster_tmp_%d" % os.getpid())['max']
	n_buffer_cells = 3

	grass.run_command("r.buffer",
					overwrite=True,
					input="distance_raster_tmp_%d" % os.getpid(),
					output="buffered_river_tmp_%d" % os.getpid(),
					distances=n_buffer_cells*res)

	grass.mapcalc("$distance_raster_buffered_tmp = if($buffered_river_tmp==2,$largest_cost_value*2,$distance_raster_tmp)",
					distance_raster_buffered_tmp = "distance_raster_buffered_tmp_%d" % os.getpid(),
					buffered_river_tmp = "buffered_river_tmp_%d" % os.getpid(),
					largest_cost_value = largest_cost_value,
					distance_raster_tmp = "distance_raster_tmp_%d" % os.getpid())

	grass.run_command("r.watershed", 
					  flags = 'm', #depends on memory!! #
					  elevation = "distance_raster_buffered_tmp_%d" % os.getpid(),
					  drainage = "flow_direction_tmp_%d" % os.getpid(),
					  stream = "stream_rwatershed_tmp_%d" % os.getpid(),
					  threshold = n_buffer_cells,
					  overwrite = True)

	
	#Calculation of stream order (Shreve/Strahler)
	grass.run_command("r.stream.order",
					  streams = "stream_rwatershed_tmp_%d" % os.getpid(),
					  dirs = "flow_direction_tmp_%d" % os.getpid(),
					  shreve = "shreve_tmp_%d" % os.getpid(),
					  strahler = "strahler_tmp_%d" % os.getpid(),
					  overwrite = True)





	
	################ Preparation Source Populations ################
	#Defining source points either as random points in river or from input raster
	if options['n_source']:
		grass.run_command("r.random",
						  overwrite=True,
						  input = "river_raster_tmp_%d" % os.getpid(),
						  n = n_source,
						  vector_output="source_points_%d" % os.getpid())
		grass.run_command("v.db.addcolumn",
					  map = "source_points_%d" % os.getpid(),
					  columns = "prob DOUBLE")


		# Set starting propability of occurence to 1.0*scalar for all random source_points	
		grass.write_command("db.execute", input="-",
					stdin = 'UPDATE source_points_%d SET prob=%d' % (os.getpid(),scalar*1.0))

	#if source population raster is provided, then use it, transform raster in vector points
	#create an attribute column "prob" and update it with the values from the raster map
	if options['source_populations']:
		#Multiplying source probability with very large scalar to avoid problems 
		#with very small floating points (problem: precision of FLOAT); needs retransforamtion in the end
		grass.mapcalc("$source_populations_scalar = $source_populations*$scalar",
							source_populations = source_populations,
							source_populations_scalar = "source_populations_scalar_%d" % os.getpid(),
							scalar = scalar)

		#Exclude source Populations that are outside the river_raster
		grass.mapcalc("$source_populations_scalar_corrected = if($river_raster_tmp,$source_populations_scalar)",
							source_populations_scalar_corrected = "source_populations_scalar_corrected_%d" % os.getpid(),
							river_raster_tmp = "river_raster_tmp_%d" % os.getpid(),
							source_populations_scalar = "source_populations_scalar_%d" % os.getpid())

		# Convert to source population points
		grass.run_command("r.to.vect",
							overwrite = True,
							input = "source_populations_scalar_corrected_%d" % os.getpid(),
							output = "source_points_%d" % os.getpid(),
							type = "point")
		grass.run_command("v.db.addcolumn",
					  map = "source_points_%d" % os.getpid(),
					  columns = "prob DOUBLE")

		#populate sample prob from input prob-raster (multiplied by scalar)
		grass.run_command("v.what.rast",
						map = "source_points_%d" % os.getpid(),
						raster = "source_populations_scalar_%d" % os.getpid(),
						column = "prob")
	
	#Adding columns and coordinates to source points
	grass.run_command("v.db.addcolumn",
					  map = "source_points_%d" % os.getpid(),
					  columns = "X DOUBLE, Y DOUBLE, segment INT, Strahler INT")					
	grass.run_command("v.to.db",
					  map = "source_points_%d" % os.getpid(),
					  type = "point",
					  option = "coor",
					  columns = "X,Y")

	

	#Convert river from vector to raster format and get cat-value
	grass.run_command("v.to.rast",
					  input = "river_vector_tmp_%d" % os.getpid(),
					  overwrite = True,
					  output = "river_raster_cat_tmp_%d" % os.getpid(),
					  use = "cat")

	#Adding information of segment to source points					 
	grass.run_command("v.what.rast",
					  map = "source_points_%d" % os.getpid(),
					  raster = "river_raster_cat_tmp_%d" % os.getpid(),
					  column = "segment")
	
	#Adding information of Strahler stream order to source points					 
	grass.run_command("v.what.rast",
					  map = "source_points_%d" % os.getpid(),
					  raster = "strahler_tmp_%d" % os.getpid(),
					  column = "Strahler") 

	
	
	########### Looping over nrun, over segements, over source points ##########
	
	if str(options['statistical_interval']) == "no":
		nrun = ['fit']
	else:
		nrun = ['fit','lwr','upr']
	

	for i in nrun:
		database = sqlite3.connect(os.path.join(gisdbase, location, mapset, 'sqlite.db'))
		#update database-connection
		db = database.cursor()

		
		mapcalc_list_B = []


		########## Loop over segments ############
		# Extract Segments-Info to loop over
		segment_list = grass.read_command("db.select", flags="c", sql= "SELECT segment FROM source_points_%d" % os.getpid()).split("\n")[:-1] # remove last (empty line)
		segment_list = map(int, segment_list)
		segment_list = sorted(list(set(segment_list)))
	
		for j in segment_list:

			segment_cat = str(j)
			grass.debug(_("This is segment nr.: " +str(segment_cat)))

			mapcalc_list_A = []

			# Loop over Source points
			source_points_list = grass.read_command("db.select", flags="c", sql= "SELECT cat, X, Y, prob, Strahler FROM source_points_%d WHERE segment=%d" % (os.getpid(),int(j))).split("\n")[:-1] # remove last (empty line)
			source_points_list = list(csv.reader(source_points_list,delimiter="|"))

			for k in source_points_list:

				cat = int(k[0])
				X = float(k[1])
				Y = float(k[2])
				prob = float(k[3])
				Strahler = int(k[4])
				coors = str(X)+","+str(Y)
				
				# Progress bar
				# add here progressbar
				



				# Debug messages
				grass.debug(_("Start looping over source points"))
				grass.debug(_("Source point coors:"+coors+" in segment nr: " +str(segment_cat)))
								
				#Select dispersal parameters
				SO = 'SO='+str(Strahler)
				grass.debug(_("This is i:"+str(i)))
				grass.debug(_("This is "+str(SO)))
				sigma_stat = fishmove.rx(i,'sigma_stat',1,1,SO,1)
				sigma_mob = fishmove.rx(i,'sigma_mob',1,1,SO,1)

				grass.debug(_("Dispersal parameters: prob="+str(prob)+", sigma_stat="+str(sigma_stat)+", sigma_mob="+str(sigma_mob)+", p="+str(p)))		

				# Getting maximum distance (cutting distance) based on truncation criterion	  
				def func(x,sigma_stat,sigma_mob,m,truncation,p):
					return p * stats.norm.cdf(x, loc=m, scale=sigma_stat) + (1-p) * stats.norm.cdf(x, loc=m, scale=sigma_mob) - truncation
				if options['truncation'] == "inf":
					max_dist = 0
				else:
					truncation = float(options['truncation'])
					max_dist = int(optimize.zeros.newton(func, 1., args=(sigma_stat,sigma_mob,m,truncation,p)))


				grass.debug(_("Distance from each source point is calculated up to a treshold of: "+str(max_dist)))

				grass.run_command("r.cost",
							  flags = 'n',
							  overwrite = True,
							  input = "river_raster_tmp_%d" % os.getpid(),
							  output = "distance_from_point_tmp_%d" % os.getpid(),
							  start_coordinates = coors,
							  max_cost = max_dist)

				

				# Getting upper and lower distance (cell boundaries) based on the fact that there are different flow lenghts through a cell depending on the direction (diagonal-orthogonal)		  
				grass.mapcalc("$upper_distance = if($flow_direction==2||$flow_direction==4||$flow_direction==6||$flow_direction==8||$flow_direction==-2||$flow_direction==-4||$flow_direction==-6||$flow_direction==-8, $distance_from_point+($ds/2.0), $distance_from_point+($dd/2.0))",
							upper_distance = "upper_distance_tmp_%d" % os.getpid(),
							flow_direction = "flow_direction_tmp_%d" % os.getpid(),
							distance_from_point = "distance_from_point_tmp_%d" % os.getpid(), 
							ds = res,
							dd = math.sqrt(2)*res,
							overwrite = True)
						
				grass.mapcalc("$lower_distance = if($flow_direction==2||$flow_direction==4||$flow_direction==6||$flow_direction==8||$flow_direction==-2||$flow_direction==-4||$flow_direction==-6||$flow_direction==-8, $distance_from_point-($ds/2.0), $distance_from_point-($dd/2.0))",
							lower_distance = "lower_distance_tmp_%d" % os.getpid(),
							flow_direction = "flow_direction_tmp_%d" % os.getpid(),
							distance_from_point = "distance_from_point_tmp_%d" % os.getpid(), 
							ds = res,
							dd = math.sqrt(2)*res,
							overwrite = True)
		

				
				# MAIN PART: leptokurtic probability density kernel based on fishmove
				grass.debug(_("Begin with core of fidimo, application of fishmove on garray"))
				
				def cdf(x):
					return (p * stats.norm.cdf(x, loc=m, scale=sigma_stat) + (1-p) * stats.norm.cdf(x, loc=m, scale=sigma_mob)) * prob
		 
		 
				#Calculation Kernel Density from Distance Raster
				#only for m=0 because of cdf-function
				if grass.find_file(name = "density_from_point_unmasked_tmp_%d" % os.getpid(), element = 'cell')['file']:
					grass.run_command("g.remove", rast = "density_from_point_unmasked_tmp_%d" % os.getpid())
				
				x1 = garray.array()
				x1.read("lower_distance_tmp_%d" % os.getpid())
				x2 = garray.array()
				x2.read("upper_distance_tmp_%d" % os.getpid())
				Density = garray.array()
				Density[...] = cdf(x2) - cdf(x1)
				grass.debug(_("Write density from point to garray. unmasked"))
				Density.write("density_from_point_unmasked_tmp_%d" % os.getpid())
		
				# Mask density output because Density.write doesn't provide nulls()
				grass.mapcalc("$density_from_point = if($distance_from_point>=0, $density_from_point_unmasked, null())",
							density_from_point = "density_from_point_tmp_%d" % os.getpid(), 
							distance_from_point = "distance_from_point_tmp_%d" % os.getpid(), 
							density_from_point_unmasked = "density_from_point_unmasked_tmp_%d" % os.getpid(),
							overwrite = True)


				# Defining up and downstream of source point
				grass.debug(_("Defining up and downstream of source point"))

				# Defining area upstream source point
				grass.run_command("r.stream.basins",
							  overwrite = True,
							  dirs = "flow_direction_tmp_%d" % os.getpid(),
							  coors = coors,
							  basins = "upstream_part_tmp_%d" % os.getpid())

				# Defining area downstream source point
				grass.run_command("r.drain",
							input = "distance_raster_tmp_%d" % os.getpid(),
							output = "downstream_drain_tmp_%d" % os.getpid(),
							overwrite = True,
							start_coordinates = coors)
				
				
				# Applying upstream split at network nodes based on inverse shreve stream order	
				grass.debug(_("Applying upstream split at network nodes based on inverse shreve stream order"))
 
				grass.mapcalc("$upstream_shreve = if($upstream_part, $shreve)",
							upstream_shreve = "upstream_shreve_tmp_%d" % os.getpid(), 
							upstream_part = "upstream_part_tmp_%d" % os.getpid(), 
							shreve = "shreve_tmp_%d" % os.getpid(),
							overwrite = True)	  
				max_shreve = grass.raster_info("upstream_shreve_tmp_%d" % os.getpid())['max']
				grass.mapcalc("$rel_upstream_shreve = $upstream_shreve / $max_shreve", 
							rel_upstream_shreve = "rel_upstream_shreve_tmp_%d" % os.getpid(), 
							upstream_shreve = "upstream_shreve_tmp_%d" % os.getpid(), 
							max_shreve = max_shreve,
							overwrite = True)

				grass.mapcalc("$division_overlay = if(isnull($downstream_drain), $rel_upstream_shreve, $downstream_drain)", 
							division_overlay = "division_overlay_tmp_%d" % os.getpid(), 
							downstream_drain = "downstream_drain_tmp_%d" % os.getpid(), 
							rel_upstream_shreve = "rel_upstream_shreve_tmp_%d" % os.getpid(),
							overwrite = True)
				grass.mapcalc("$density = if($density_from_point, $density_from_point*$division_overlay, null())",
							density = "density_"+str(cat),
							density_from_point = "density_from_point_tmp_%d" % os.getpid(),
							division_overlay = "division_overlay_tmp_%d" % os.getpid(),
							overwrite = True)
				
				grass.run_command("r.null", map="density_"+str(cat), null="0")
				
				

				###### Barriers per source point #######
				if options['barriers']:
					grass.mapcalc("$distance_upstream_point = if($upstream_part, $distance_from_point, null())",
								distance_upstream_point = "distance_upstream_point_tmp_%d" % os.getpid(),
								upstream_part ="upstream_part_tmp_%d" % os.getpid(),
								distance_from_point = "distance_from_point_tmp_%d" % os.getpid(),
								overwrite = True)

					#Getting distance of barriers and information if barrier is involved/affected
					grass.run_command("v.what.rast",
								map = "barriers_%d" % os.getpid(),
								raster = "distance_upstream_point_tmp_%d" % os.getpid(),
								column = "dist")
									

					# Loop over the affected barriers (from most downstream barrier to most upstream barrier)
					# Initally affected = all barriers where density > 0
					barriers_list = grass.read_command("db.select", flags="c", sql= "SELECT cat, new_X, new_Y, dist, %s FROM barriers_%d WHERE dist > 0 ORDER BY dist" % (passability_col,os.getpid())).split("\n")[:-1] # remove last (empty line)
					barriers_list = list(csv.reader(barriers_list,delimiter="|"))

					#if affected barriers then define the last loop (find the upstream most barrier)
					if barriers_list:					
						last_barrier = float(barriers_list[-1][3])

					for l in barriers_list:

						cat = int(l[0])
						new_X = float(l[1])
						new_Y = float(l[2])
						dist = float(l[3])
						passability = float(l[4])				
						coors_barriers = str(new_X)+","+str(new_Y)

						grass.debug(_("Starting with calculating barriers-effect (coors_barriers: "+coors_barriers+")"))

						#Defining upstream the barrier
						grass.run_command("r.stream.basins",
								overwrite = True,
								dirs = "flow_direction_tmp_%d" % os.getpid(),
								coors = coors_barriers,
								basins = "upstream_barrier_tmp_%d" % os.getpid())

						grass.run_command("r.null", map="density_"+str(cat), setnull="0")
				
						#Getting density upstream barrier only
						grass.mapcalc("$upstream_barrier_density = if($upstream_barrier, $density, null())",
								upstream_barrier_density = "upstream_barrier_density_tmp_%d" % os.getpid(), 
								upstream_barrier = "upstream_barrier_tmp_%d" % os.getpid(), 
								density = "density_"+str(cat),
								overwrite = True)
							
						#Getting sum of upstream density and density to relocate downstream
						d = {'n':5, 'min': 6, 'max': 7, 'mean': 9, 'sum': 14, 'median':16, 'range':8}
						univar_upstream_barrier_density = grass.read_command("r.univar", map = "upstream_barrier_density_tmp_%d" % os.getpid(), flags = 'e')
						if univar_upstream_barrier_density:
							sum_upstream_barrier_density = float(univar_upstream_barrier_density.split('\n')[d['sum']].split(':')[1])
						else:
							grass.fatal(_("Error with upstream density/barriers. The error occurs for coors_barriers (X,Y): "+coors_barriers))		


						density_for_downstream = sum_upstream_barrier_density*(1-passability)
				
	
						# barrier_effect = Length of Effect of barriers (linear decrease up to max (barrier_effect)
						barrier_effect=200 #units as in mapset (m)
				
						# Calculating distance from barriers (up- and downstream)
						grass.run_command("r.cost",
									overwrite = True,
									input = "river_raster_tmp_%d" % os.getpid(),
									output = "distance_barrier_tmp_%d" % os.getpid(),
									start_coordinates = coors_barriers,
									max_cost=barrier_effect)


						# Getting distance map for downstream of barrier only
						grass.mapcalc("$distance_downstream_barrier = if(isnull($upstream_barrier), $distance_barrier, null())",
									distance_downstream_barrier = "distance_downstream_barrier_tmp_%d" % os.getpid(),
									upstream_barrier = "upstream_barrier_tmp_%d" % os.getpid(), 
									distance_barrier = "distance_barrier_tmp_%d" % os.getpid(),
									overwrite = True)

						# Getting inverse distance map for downstream of barrier only
						grass.mapcalc("$inv_distance_downstream_barrier = 1.0/$distance_downstream_barrier",
									inv_distance_downstream_barrier = "inv_distance_downstream_barrier_tmp_%d" % os.getpid(),
									distance_downstream_barrier = "distance_downstream_barrier_tmp_%d" % os.getpid(),
									overwrite = True)

						# Getting parameters for distance weighted relocation of densities downstream the barrier (inverse to distance (reciprocal), y=(density/sum(1/distance))/distance)
						univar_distance_downstream_barrier = grass.read_command("r.univar", map = "inv_distance_downstream_barrier_tmp_%d" % os.getpid(), flags = 'e')
						sum_inv_distance_downstream_barrier = float(univar_distance_downstream_barrier.split('\n')[d['sum']].split(':')[1])
						grass.debug(_("sum_inv_distance_downstream_barrier: "+str(sum_inv_distance_downstream_barrier)))
												

						#Calculation Density downstream the barrier	
						grass.mapcalc("$downstream_barrier_density = ($density_for_downstream/$sum_inv_distance_downstream_barrier)/$distance_downstream_barrier",
									downstream_barrier_density = "downstream_barrier_density_tmp_%d" % os.getpid(),
									density_for_downstream=density_for_downstream,
									sum_inv_distance_downstream_barrier = sum_inv_distance_downstream_barrier,
									distance_downstream_barrier = "distance_downstream_barrier_tmp_%d" % os.getpid(),
									overwrite = True)				

						# Combination upstream and downstream density from barrier
						grass.run_command("r.null", map="density_"+str(cat), null="0")
						grass.run_command("r.null", map="downstream_barrier_density_tmp_%d" % os.getpid(), null="0")
					
						grass.mapcalc("$density_point = if(isnull($upstream_barrier), $downstream_barrier_density+$density_point, $upstream_barrier_density*$passability)",
									density_point = "density_"+str(cat), 
									upstream_barrier = "upstream_barrier_tmp_%d" % os.getpid(), 
									downstream_barrier_density = "downstream_barrier_density_tmp_%d" % os.getpid(),
									upstream_barrier_density = "upstream_barrier_density_tmp_%d" % os.getpid(),
									passability=passability,
									overwrite = True)
								
						if dist == last_barrier :
							grass.run_command("r.null", map="density_"+str(cat), null="0")
						else:
							grass.run_command("r.null", map="density_"+str(cat), setnull="0")
					
						#If the barrier in the loop was impermeable (passability=0) 
						#than no more upstream barriers need to be considered --> break
						if passability == 0:
							grass.run_command("r.null", map="density_"+str(cat), null="0")
							break


				# Get a list of all densities processed so far within this segement
				mapcalc_list_A.append("density_"+str(cat))	
			
			mapcalc_string_A_aggregate = "+".join(mapcalc_list_A)
			mapcalc_string_A_removal = ",".join(mapcalc_list_A)
		 
			grass.mapcalc("$density_segment = $mapcalc_string_A_aggregate",
							density_segment = "density_segment_"+segment_cat,
							mapcalc_string_A_aggregate = mapcalc_string_A_aggregate,
							overwrite = True)
			
			grass.run_command("g.remove", rast = mapcalc_string_A_removal, flags ="f")
			
			grass.run_command("r.null", map="density_segment_"+segment_cat, null="0") # Final density map per segment, set 0 for aggregation with r.mapcalc
							 
			mapcalc_list_B.append("density_segment_"+segment_cat)


		 
		mapcalc_string_B_aggregate = "+".join(mapcalc_list_B)
		mapcalc_string_B_removal = ",".join(mapcalc_list_B)
	   
		# Final raster map, Final map is sum of all 
		# density maps (for each segement), All contributing maps (string_B_removal) are deleted
		# in the end.
		grass.mapcalc("$density_final = $mapcalc_string_B_aggregate",
						density_final = "density_final_%d" % os.getpid(),
						mapcalc_string_B_aggregate = mapcalc_string_B_aggregate,
						overwrite = True)

		# backtransformation (divide by scalar which was defined before)
		grass.mapcalc("$density_final_corrected = $density_final/$scalar",
						density_final_corrected = "density_final_corrected_%d" % os.getpid(),
						density_final = "density_final_%d" % os.getpid(),
						scalar = scalar)

		grass.run_command("g.copy", 
			rast = "density_final_corrected_%d" % os.getpid() + "," + output_fidimo+"_"+i)
		
		
		# Set all 0-values to NULL, Backgroundvalues			
		grass.run_command("r.null", map=output_fidimo+"_"+i, setnull="0")
	
	
		grass.run_command("g.remove", rast = mapcalc_string_B_removal, flags ="f")
			

	# Make source_points and barriers permanent	 
	grass.run_command("g.copy", 
		vect = "source_points_%d" % os.getpid() + "," + output_fidimo + "_source_points")
	if options['barriers']:
		grass.run_command("g.copy", 
			vect = "barriers_%d" % os.getpid() + "," + output_fidimo + "_barriers")
		
	if flags['b']:
		grass.run_command("g.remove", vect = output_fidimo + "_source_points", flags ="f")
		if options['barriers']:
			grass.run_command("g.remove", vect = output_fidimo + "_barriers", flags ="f")
	
				
	return 0


if __name__ == "__main__":
	options, flags = grass.parser()
	atexit.register(cleanup)
	sys.exit(main())
