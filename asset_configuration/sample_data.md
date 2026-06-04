sample_data:

1. 4 个 block_entrance (public_space_type):
   - public_space_geometry(represented by rectangle): (0,0),(10,10)
     - public_space_segments:  (0,0),(0,10), block_boundary_primary
     - public_space_segments:  (0,10),(10,10), street_boundary_primary
     - public_space_segments:  (10,10),(10,0), street_boundary_primary
     - public_space_segments:  (10,0),(0,0), block_boundary_other
   - public_space_geometry(represented by rectangle): (0,90),(10,110)
     - public_space_segments:  (0,90),(10,90), street_boundary_primary
     - public_space_segments:  (10,90),(10,110), street_boundary_primary
     - public_space_segments:  (10,110),(0,110), street_boundary_primary
     - public_space_segments:  (0,110),(0,90), block_boundary_other
   - public_space_geometry(represented by rectangle): (0,190),(10,200)
     - public_space_segments:  (0,190),(10,190) , street_boundary_primary
     - public_space_segments:  (10,190),(10,200) , street_boundary_primary
     - public_space_segments:  (10,200),(0,200), block_boundary_other
     - public_space_segments:  (0,200),(0,190), block_boundary_other
   - public_space_geometry(represented by rectangle): (90,190),(100,200)
     - public_space_segments:  (90,190),(100,190) , street_boundary_primary
     - public_space_segments:  (100,190),(100,200), block_boundary_secondary
     - public_space_segments:  (100,200),(90,200), block_boundary_other
     - public_space_segments:  (90,200),(90,190) , street_boundary_primary
2. 4 个 city_street_roof (public_space_type):
   - public_space_geometry(represented by rectangle): (10,4),(70,10)
     - public_space_segments:  (10,4),(70,4) , street_boundary_secondary
     - public_space_segments:  (70,4),(70,10), yard_boundary
     - public_space_segments:  (70,10),(60,10), street_boundary_primary
     - public_space_segments:  (60,10),(10,10),building_wall
     - public_space_segments:  (10,10),(10,4) , block_entrance
     - add column (间隔为4米，柱子为0.6×0.6的方形) in Asset_has_set in the public_space_segments:  (10,4),(70,4) 
   - public_space_geometry(represented by rectangle): (4,10),(10,90)
     - public_space_segments:  (4,10),(10,10) , block_entrance
     - public_space_segments:  (10,10),(10,90),building_wall
     - public_space_segments:  (10,90),(4,90), block_entrance
     - public_space_segments:  (4,90),(4,10) , street_boundary_secondary
     - add column (间隔为4米，柱子为0.6×0.6的方形) in Asset_has_set in the public_space_segments:   (4,90),(4,10)
   - public_space_geometry(represented by rectangle): (4,110),(10,190)
     - public_space_segments:  (4,110),(10,110) , block_entrance
     - public_space_segments:  (10,110),(10,190), building_wall
     - public_space_segments:  (10,190),(4,190), block_entrance
     - public_space_segments:  (4,190),(4,110) ,  street_boundary_secondary
     - add column (间隔为4米，柱子为0.6×0.6的方形) in Asset_has_set in the public_space_segments:    (4,190),(4,110) 
   - public_space_geometry(represented by rectangle): (60,10),(70,90)
     - public_space_segments:  (60,10),(70,10) ,  street_boundary_secondary
     - public_space_segments:  (70,10),(70,90), yard_boundary
     - public_space_segments:  (70,90),(60,90), yard_boundary
     - public_space_segments:  (60,90),(60,70) , building_entrance_main
     - public_space_segments:  (60,70),(60,10) , building_wall
     - add column (间隔为4米，柱子为0.6×0.6的方形) in Asset_has_set in the public_space_segments:  (70,10),(70,90) 
3. 5 个 city_street_roofless (public_space_type):
   - public_space_geometry(represented by rectangle): (10,0),(70,4)
     - public_space_segments:  (10,0),(70,0) , block_boundary_primary
     - public_space_segments:  (70,0),(70,4) , yard_boundary
     - public_space_segments:  (70,4),(10,4) , street_boundary_secondary
     - public_space_segments:  (10,4),(10,0) , block_entrance
   - public_space_geometry(represented by rectangle): (0,10),(4,90)
     - public_space_segments:  (0,10),(4,10) , block_entrance
     - public_space_segments:  (4,10),(4,90) , building_other_type
     - public_space_segments:  (4,90),(0,90) , block_entrance
     - public_space_segments:  (0,90),(0,10) , block_boundary_other
   - public_space_geometry(represented by rectangle): (0,110),(4,190)
     - public_space_segments:  (0,110),(4,110) , block_entrance
     - public_space_segments:  (4,110),(4,190) ,building_other_type
     - public_space_segments:  (4,190),(0,190) , block_entrance
     - public_space_segments:  (0,190),(0,110) , block_boundary_other
   - public_space_geometry(represented by rectangle): (10,190),(90,200)
     - public_space_segments:  (10,190),(90,190) , building_wall
     - public_space_segments:  (90,190),(90,200) , block_entrance
     - public_space_segments:  (90,200),(10,200) , block_boundary_other
     - public_space_segments:  (10,200),(10,190) , block_entrance
   - public_space_geometry(represented by rectangle): (90,110),(100,190)
     - public_space_segments:  (90,110),(100,110) , block_entrance
     - public_space_segments:  (100,110),(100,190) , block_boundary_secondary
     - public_space_segments:  (100,190),(90,190) , block_entrance
     - public_space_segments:  (90,190),(90,110) , building_wall
4. 1 个city_yard_roof
   - public_space_geometry(represented by rectangle): (10,90),(70,110)
     - public_space_segments:  (10,90),(50,90) , building_wall
     - public_space_segments:  (50,90),(60,90) , building_entrance_main
     - public_space_segments:  (60,90),(70,90) , street_boundary_primary
     - public_space_segments:  (70,90),(70,110) , yard_boundary
     - public_space_segments:  (70,110),(60,110) , building_wall
     - public_space_segments:  (60,110),(50,110) , building_entrance_main
     - public_space_segments:  (50,110),(10,110) , building_wall
     - public_space_segments:  (10,110),(10,90) , block_entrance
5. 1个city_yard_roofless
   - public_space_geometry(represented by rectangle): (70,0),(100,110)
     - public_space_segments:  (70,0),(100,0) , block_boundary_primary
     - public_space_segments:  (100,0),(100,110) , block_boundary_secondary
     - public_space_segments:  (100,110),(90,110) , block_entrance
     - public_space_segments:  (90,110),(70,110) , building_wall
     - public_space_segments:  (70,110),(70,90) , yard_boundary
     - public_space_segments:  (70,90),(70,10) , street_boundary_secondary
     - public_space_segments:  (70,10),(70,0) , street_boundary_primary
6. 2个building_entrance
   - public_space_geometry(represented by rectangle): (50,70),(60,90)
     - public_space_segments:  (50,70),(60,70) , building_other_type
     - public_space_segments:  (60,70),(60,90) , building_entrance_main
     - public_space_segments:  (60,90),(50,90) , building_entrance_main
     - public_space_segments:  (50,90),(50,80) , building_other_type
     - public_space_segments:  (50,80),(50,70) , building_wall
   - public_space_geometry(represented by rectangle): (50,110),(60,140)
     - public_space_segments:  (50,110),(60,110) , building_entrance_main
     - public_space_segments:  (60,110),(60,140) , building_wall
     - public_space_segments:  (60,140),(50,140) , building_other_type
     - public_space_segments:  (50,140),(50,110) , building_wall



