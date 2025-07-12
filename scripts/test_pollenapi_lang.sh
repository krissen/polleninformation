#!/bin/bash
for L in {0..10}; do
  echo -n "L=$L: "
  curl -s "https://www.polleninformation.at/index.php?id=536&type=15976824&L=$L&tx_scapp_appapi%5Baction%5D=getFullContaminationData&locationType=gps&C=26&personal_contamination=false&sensitivity=0&country=SE&sessionid=&pasyfo=0&value%5Blatitude%5D=59.334&value%5Blongitude%5D=18.0632" \
    -H 'Accept: application/json, text/plain, */*' \
    -H 'User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148' \
    | jq -r '.result.contamination_date_1 // "NO RESPONSE"'
done

