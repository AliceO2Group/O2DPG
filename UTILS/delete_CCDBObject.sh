OBJECT=${1}
# object is of the form PATH/VALIDITY/ID
# Users/s/swenzel/MCProdInfo/LHC24d1c_minus50/529663/55ceab78-485e-11f0-8e6c-c0a80209250c

curl -X DELETE --cert /tmp/tokencert_$(id -u).pem \
     --key /tmp/tokenkey_$(id -u).pem   \
     -v -k                              \
     "http://ccdb-test.cern.ch:8080/${OBJECT}"

