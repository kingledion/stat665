import mysql.connector
from subway_assignments import zip_assigns
import parse_functions as pf


#################################################################
# NOTE
#   Requires mysql installed on your computer using the standard ports
#   For mysql, create a database and a user 
#   with username and password as defined below. This user must be 
#   given 'GRANT ALL ON db_name'.

# List of all data fields being filled with census data. MySQL data type is 'INT'.
fields = ['population',
          'pop_child',
          'pop_old',
          'employment',
          'hunits',
          'hvacant',
          'sing_det',
          'sing_att',
          'duplex',
          'three_four',
          'five_nine',
          'ten_nineteen',
          'twenty_plus',
          '2014_later',
          '2010_2013',
          '2000_2009',
          '1990_1999',
          '1980_1989',
          '1970_1979',
          '1960_1969',
          '1950_1959',
          '1940_1949',
          '1939_older']

def opendb():
    db = mysql.connector.connect(user='dbuser', password='dbpass', database='zipcode')
    cursor = db.cursor()
    return db, cursor

def main():

    zip_db, zip_cursor = opendb() 
        
    create_db(zip_db, zip_cursor)
    
    data = read_files()
    data = assign_zips(data)
    insert_data(zip_db, zip_cursor, data)
    fix_no_geo_data(zip_db, zip_cursor)
    
    
def create_db(zip_db, zip_cursor):
    
    zip_cursor.execute("DROP TABLE IF EXISTS zip_housing;")
    censusfields = [f + " INT DEFAULT 0" for f in fields]
    sql = "CREATE TABLE zip_housing (zipcode VARCHAR(8) NOT NULL PRIMARY KEY, name VARCHAR(32), "
    sql += "area FLOAT, {0}, location POINT)".format(", ".join(censusfields))
    zip_cursor.execute(sql)
        
    zip_cursor.execute("DROP FUNCTION IF EXISTS haversine;")
    sql = "CREATE FUNCTION haversine(lat1 FLOAT, lon1 FLOAT, lat2 FLOAT, lon2 FLOAT) RETURNS FLOAT NO SQL DETERMINISTIC COMMENT "
    sql += "'Returns the distance in degrees on the Earth between two known points of latitude and longitude' BEGIN "
    sql += "RETURN DEGREES(ACOS(COS(RADIANS(lat1)) * COS(RADIANS(lat2)) * COS(RADIANS(lon2) - RADIANS(lon1)) + SIN(RADIANS(lat1)) * SIN(RADIANS(lat2))));"
    sql += "END;"
    zip_cursor.execute(sql)
    
    zip_db.commit()
    
    
def read_files():
    
    data = {}
   
    # Loop through all 'read_xxx' functions and run them all; combine the returned data    
    for fn in [func for func in dir(pf) if func.startswith("read_")]:   
        for key,val in getattr(pf, fn)().items():
            if key in data:
                data[key].update(val)
            else:
                data[key] = val
        print("Finished parsing", fn)
       
    # Ensure all values get the zipcode tag, no matter what source they were read from
    for key in data:
        data[key].update({'zipcode': key})
        
    # Loop through all 'postproc_xxx' functions and run them all; combine the returned data    
    for fn in [func for func in dir(pf) if func.startswith("postproc_")]:   
        data = getattr(pf, fn)(data)
        print("Finished post processing", fn)
    
    return data

def merge_data(primary, toadd):
    keys = list((set(primary.keys()) | set(toadd.keys())) - set(['zipcode', 'name', 'location']))
    for k in keys:
        if k in primary and k in toadd:
            primary[k] = primary[k] + toadd[k]
        elif k in toadd:
            primary[k] = toadd[k]
    
# Resolve high employment data with no geo location:
def assign_zips(data):
    for key in zip_assigns:
        if 'pop' in data[key]:
            print("This one has a pop! {0}".format(key))
            input()
        else:
            merge_data(data[zip_assigns[key]], data[key])
            del data[key]
            
    return data
            
        
def insert_data(zip_db, zip_cursor, data):
          
    key_names = ['zipcode', 'name', 'area'] + fields + ['location']       
    query = "INSERT INTO zip_housing ({0}) VALUES ({1});"

    count = 0  
    
    for key in data:
        
        count += 1
        
        d = data[key]
        vals = [d[k] if k in d else 0 for k in key_names]
        use_fields = [key_names[i] for i in range(len(key_names)) if vals[i]]
        use_vals = [v for v in vals if v]
        # USE BATCHING!!!! SO SLOW!!!
        zip_cursor.execute(query.format(", ".join(use_fields), ", ".join(["'" + str(v) + "'" for v in use_vals[:2]]+[str(v) for v in use_vals[2:]])))

        prog = count / len(data)
        print("\rInserting into database: [{0:10s}] {1:.1f}%".format('#' * int(prog * 10) , prog*100), end="", flush=True)

    print()
    zip_db.commit()
    

# Resolve data with no geo
def fix_no_geo_data(zip_db, zip_cursor):
    
    field_sums = ", ".join(["SUM({0})".format(f) for f in fields])
    
    zip_cursor.execute("SELECT name, {0} FROM zip_housing WHERE location IS NULL GROUP BY name;".format(field_sums))
    
    city_list = [(row[0], row[1:]) for row in zip_cursor.fetchall()]

    count = 0
    for name, field_vals in city_list:
        count += 1
        
        zip_cursor.execute("SELECT zipcode, employment / area AS density FROM zip_housing WHERE name = '{0}' and area IS NOT NULL ORDER BY density desc;".format(name))
        zip_list = zip_cursor.fetchall()
        
        if len(zip_list) > 0:
            i = 0
            while i < len(zip_list) and zip_list[i][1] > 1000:
                i+= 1
            if i > 0:
                zip_list = [z[0] for z in zip_list[:i]]
            else:
                zip_list = ["'" + z[0] + "'" for z in zip_list]

            updates = [(fld, val/len(zip_list)) for fld, val in zip(fields, field_vals)]
            update_string = ", ".join(["{0} = {0} + {1}".format(fld, val) for fld, val in updates])
            zip_cursor.execute("UPDATE zip_housing SET {0} WHERE zipcode in ({1});".format(update_string,  ", ".join(zip_list)))
        else:
            pass
            # WHAT ARE WE DOING HERE???? WE ARE LETTING THESE ZIP CODES JUST DROP

        prog = count/len(city_list)
        print("\rResolving null areas: [{0:10s}] {1:.1f}%".format('#' * int(prog * 10) , prog*100), end="", flush=True)
        
    print()
    zip_db.commit()
    
    zip_cursor.execute("DELETE FROM zip_housing WHERE location IS NULL;")
    zip_db.commit() 
       
    zip_db = mysql.connector.connect(user='root', password='city4533', database='zipcode')
    zip_cursor = zip_db.cursor()
    
    zip_cursor.execute("ALTER TABLE zip_housing MODIFY location POINT NOT NULL;")
    zip_cursor.execute("CREATE SPATIAL INDEX location_index ON zip_housing (location);")
    zip_db.commit()       

     

main()


