> [English](README.en.md) | 涓枃

# D750 1080p 楂樼爜鐜囦慨鏀癸紙64/60 Mbps锛?
> **鑼冨洿澹版槑**锛氭湰鏂囦笌 `bitrate/` 宸ュ叿鍙仛**鏈湴闈欐€佷慨鏀逛笌瀹瑰櫒绾ч獙璇?*锛?> 涓嶅寘鍚浐浠躲€佸瘑閽ャ€佽В瀵嗛暅鍍忔垨鏀瑰悗闀滃儚銆傜浉鏈哄疄鎷嶆湭楠岃瘉锛涘埛鏈洪闄╄嚜璐熴€?> 璇﹁ [CONTRIBUTING.md](../CONTRIBUTING.md) 涓?[NOTICE.md](../NOTICE.md)銆?
## 1. 缁撹

| 椤圭洰 | 缁撴灉 |
| --- | --- |
| 鐩爣 | Nikon D750锛宍D750_0115`锛?.15锛夛紝妯″潡 `b1010_115a.bin` |
| 淇敼琛?| 鏂囦欢鍋忕Щ `0x2AA9AC`锛?8 瀛楄妭/椤癸紝1080p 缁勫叡 9 椤?|
| 鍛戒腑琛?| entry 1 / 3 / 5 / 7 / 9锛圚Q 琛岋級 |
| 淇敼鍓?| `42/35`銆乣42/35`銆乣24/20`銆乣24/20`銆乣24/20` Mbps |
| 淇敼鍚?| 鍏ㄩ儴 `64/60` Mbps锛坄0x03D09000` / `0x03938700`锛?|
| 鏈敼鍔?| 4 涓?NQ 琛屻€乪ntry 10 璧风殑浣庡垎杈ㄧ巼缁勩€佸彟澶栦袱涓ā鍧?|
| 妯″潡 CRC | `0x12CA` 鈫?`0x4314` |
| 鍖?CRC | `0x7EE4` 鈫?`0x7EE4`锛圕RC residue 鎬ц川锛屼笉鏄病鏀瑰埌锛岃 搂3锛?|
| 瑙ｅ瘑闀滃儚宸紓 | 36 B锛?4 B 鐮佺巼瀛楁 + 2 B 妯″潡 CRC锛涘瓧娈靛 0 B |
| QEMU M0 鍥炲綊 | 涓?stock 涓€鑷达細exit 0銆佸悓涓€ halt 瀵勫瓨鍣ㄣ€? MMIO銆? UART |
| 鐩告満瀹炴媿 | **鏈獙璇?* |

## 2. 琛ㄩ」涓庡亸绉?
`b1010_115a.bin` 涓?1080p 缁勪粠 `0x2AA9AC` 寮€濮嬶細

```
entry 1  0x2AA9AC
entry 2  0x2AA9C8
entry 3  0x2AA9E4
entry 4  0x2AAA00
entry 5  0x2AAA1C
entry 6  0x2AAA38
entry 7  0x2AAA54
entry 8  0x2AAA70
entry 9  0x2AAA8C
entry 10 0x2AAAA8   <- 涓婇檺闄嶅埌 47.19 Mbps锛屾帹鏂负 720p/480p 缁勶紝鏈敼
```

姣忛」鍓嶄袱涓?little-endian u32 鏄袱妗ｇ爜鐜囷紝闅忓悗鏄?`flag=1`銆佽椤逛笂闄?锛?080p 缁?`0x04380780` = 70,780,800 bps锛夈€佷互鍙婃椂闂村熀/甯х巼瀛楁銆?64/60 Mbps 浣庝簬 70,780,800 鐨勪笂闄愩€?
杩欎釜鈥? 涓?HQ 琛屸€濈殑鏄犲皠涓?Nikon Hacker 鐨?D810 1.14 琛ヤ竵鍚屾瀯锛欴810 鐨?`Video 1080 HQ 64mbps` 涔熸槸鏀?entry 1/3/5/7/9锛屽啓 `64,000,000 / 60,000,000`锛?涓ゆ満鐨勮〃閮芥槸 28 瀛楄妭/椤广€佸瓧娈甸『搴忎笌涓婇檺鐩稿悓銆?
## 3. 楠岃瘉

淇敼鍣?`bitrate/d750_bitrate_patch.py` 鍦ㄥ啓鍏ュ墠寮哄埗鏍稿锛?
1. 5 涓?HQ 琛岀殑 stock 鍊煎繀椤绘槸 `42/35` 鎴?`24/20`锛?2. 姣忚 `flag == 1`銆佷笂闄愪负 70,780,800锛?3. 鐩爣 64/60 蹇呴』浣庝簬涓婇檺锛?4. 鏀瑰悗閲嶈В鏋愶紝5 琛屽繀椤昏鍥?64/60锛?5. 4 涓?NQ 琛岄€愬瓧鑺備笉鍙橈紱
6. 宸紓鍙兘钀藉湪 5 琛?脳 2 涓?u32 瀛楁鍐呫€?
鏈湴鐙珛楠岃瘉锛坄d750_bitrate_verify.py`锛屼笉闅忎粨搴撴彁渚涳紝鍥犱负瀹冮渶瑕佸瘑閽ヤ笌
瑙ｅ瘑鍣級缁撴灉锛?
```
stock   image sha256 6c1dfadc8feb38bc783522c37f6351e1e8006f4684c8234690afb9aa08444859
patched image sha256 9c88f3cc80e5e19d780055ced0e4e539739f0e858af1e831228e5f19e904988a
module  sha256       ea0c161dd8bfc7fdd7037c13005e8a4f7f3ddf98a79c9565e2c8aa973ba3f579
package CRC 0x7EE4 -> 0x7EE4
b1010 CRC   0x12CA -> 0x4314
changed decrypted bytes: 36 (fields+CRCs), outside: 0
HQ rows at target:
  entry 1 @0x2AA9AC  64000000 / 60000000
  entry 3 @0x2AA9E4  64000000 / 60000000
  entry 5 @0x2AAA1C  64000000 / 60000000
  entry 7 @0x2AAA54  64000000 / 60000000
  entry 9 @0x2AAA8C  64000000 / 60000000
all checks passed
```

**涓轰粈涔堝寘 CRC 娌″彉锛?* CRC-16 鐨?residue 鎬ц川浣?`CRC16(payload || CRC16(payload)) == 0`锛涙瘡涓ā鍧楁湯灏惧甫鑷繁鐨?CRC锛屽寘 CRC 瀵?鈥滄ā鍧?payload 鍙樺寲 + 妯″潡 CRC 閲嶇畻鈥濅笉鏁忔劅銆俻ayload 纭疄鍙樹簡锛岃瘉鎹槸妯″潡 CRC
`0x12CA 鈫?0x4314` 鍜?36 B 宸紓锛岃€屼笉鏄寘 CRC銆?
## 4. 鍝堝笇

| 鏂囦欢 | 澶у皬 | SHA-256 |
| --- | ---: | --- |
| `D750_0115.bin`锛坰tock 鍔犲瘑闀滃儚锛?| 21,552,187 | `6c1dfadc鈥?8444859` |
| `D750_0115.hq64.bin`锛堟敼鍚庨暅鍍忥紝鏈湴锛?| 21,552,187 | `9c88f3cc鈥904988a` |
| `b1010_115a.bin`锛坰tock 妯″潡锛?| 20,324,448 | `faada7fe鈥82937fd` |
| `b1010_115a.hq64.bin`锛堟敼鍚庢ā鍧楋紝鏈湴锛?| 20,324,448 | `ea0c161d鈥a3f579` |
| `D750_0115.dec`锛坰tock 瑙ｅ瘑锛?| 21,552,187 | `1ec77111鈥?c749bdd` |
| `D750_0115.hq64.dec`锛堟敼鍚庤В瀵嗭級 | 21,552,187 | `79e59294鈥?2ca1c300` |

瀹屾暣鍝堝笇瑙佹湰鍦?`D750_0115.hq64.out/verify_report.json`锛涗粨搴撲笉鍖呭惈杩欎簺闀滃儚銆?
## 5. 宸ュ叿

```sh
# 鍙鏌ヨ〃
python bitrate/d750_bitrate_patch.py \
  --module D750_0115.dec.modules/b1010_115a.bin --check

# 鐢熸垚鏀瑰悗妯″潡
python bitrate/d750_bitrate_patch.py \
  --module D750_0115.dec.modules/b1010_115a.bin \
  --out b1010_115a.hq64.bin --json patch_report.json

# 鍗曞厓娴嬭瘯锛堥渶瑕佹湰鍦版ā鍧楋級
D750_MODULE=/path/to/b1010_115a.bin python bitrate/test_d750_bitrate_patch.py
```

閲嶆墦鍖?/ 閲嶆柊鍔犲瘑 / 瀹瑰櫒 CRC 涓嶅湪鏈粨搴撳伐鍏峰唴锛氬畠闇€瑕佷綘鑷繁鍚堟硶鎸佹湁鐨?瀵嗛挜涓庤В瀵嗗櫒锛涙湰浠撳簱涓嶆彁渚涘瘑閽ャ€佽В瀵嗗櫒鎴栨敼鍚庨暅鍍忋€?
## 6. 椋庨櫓涓庢湭楠岃瘉椤?
1. **缂栫爜鍣?鍐欏崱/鍥炴斁鏈獙璇併€?* 64 Mbps 瀵?1080p30 鏄?stock 24 Mbps 鐨勭害
   2.7 鍊嶏紱鐩告満鍙兘鍦ㄦ參鍗′笂鎻愬墠鍋滄銆佸綍鍑虹數鑴戣兘鎾絾鐩告満涓嶈兘鍥炴斁鐨勬枃浠讹紝
   鎴栧洜鍙戠儹/缂栫爜鍣ㄤ笂闄愰檷鐮佺巼銆?2. **绛惧悕/鏇存柊鍣ㄦ湭楠岃瘉銆?* 鏈伐鍏峰彧淇濊瘉瀹瑰櫒 CRC 鑷唇锛汥750 鏇存柊鍣ㄦ槸鍚﹀彟鏈?   鍨嬪彿/绛惧悕妫€鏌ユ湭鐭ワ紝鏀瑰悗闀滃儚涓嶄繚璇佽鐩告満鎺ュ彈銆?3. **涓嶈鎷垮敮涓€涓€鍙板伐浣滄満璇曘€?* 淇濈暀 stock 闀滃儚锛涚‘璁ょ數閲忋€佷娇鐢ㄥ凡鐭ヨ壇濂界殑
   UHS-I 鍗°€佸厛鐭綍 10鈥?0 绉掞紝妫€鏌ョ爜鐜囦笌鍥炴斁銆?4. 鏈鍙敼 1080p 鐨?5 涓?HQ 琛岋紱NQ 浠嶆槸 24/20 涓?12/10锛?20p/480p 缁勬湭鍔ㄣ€?
## 7. 鍙傝€?
- Nikon Hacker D810 1.14 琛ヤ竵瀹氫箟锛坄Video 1080 HQ 64mbps`锛夛細
  <https://github.com/simeonpilgrim/nikon-firmware-tools>
- 楂樼爜鐜囪鏄庯細
  <https://simeonpilgrim.com/blog/2014/02/23/high-bit-rate-recording-now-solved/>
- QEMU 鍥炲綊瑙?[../docs/validation.md](../docs/validation.md) 涓?  [../evidence/](../evidence/)銆?