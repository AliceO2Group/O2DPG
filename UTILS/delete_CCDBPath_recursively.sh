# Step 1 we browse the complete MCProd (or whatever) subfolder

P=$1

BROWSE_RESULT=$(curl --cert /tmp/tokencert_$(id -u).pem \
     --key /tmp/tokenkey_$(id -u).pem   \
     -v -k                              \
     "http://ccdb-test.cern.ch:8080/browse/${P}/*" | awk -F': ' '
/^ID:/ {id=$2}
/^Path:/ {path=$2}
/^Validity:/ {split($2, a, " -"); validity=a[1]; print path "/" validity "/" id}
')

for path in ${BROWSE_RESULT}; do
 echo "Will,Would delete ${path}"
 ./delete_CCDBObject.sh ${path}
done
