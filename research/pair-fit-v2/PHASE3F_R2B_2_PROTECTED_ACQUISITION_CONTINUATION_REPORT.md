# Phase 3F-R2B.2 Correction-Only Protected Acquisition Continuation Report

## CONDITIONAL PASS — acquisition complete; unresolved team evidence requires a separate checkpoint

Phase 3F-R2B.2 completed its single official invocation. Atlanta Base was revalidated only from the original R2B bytes, and the exact 59 network-authorized identities at original ordinals 2–60 each completed one verified HTTP 200 attempt. Indiana and Memphis returned exactly 250 rows in both measures and remain unresolved. This classification covers acquisition and structural reconciliation only; it is not final-test readiness or model performance.

## 1. Repository and permanent history

- Branch: `research/pair-fit-v2`
- Committed HEAD: `1d98c20f41fe550deafa7e68cba611d7d66bf519`
- Upstream: `origin/research/pair-fit-v2`
- Ahead/behind: `0/0`
- Starting index and working tree: clean
- Final index: clean
- Final working tree: only the intended `.gitignore`, R2B.2 policy, report, implementation, CLI, and focused test changes
- Commit or push: none

Original Phase 3F-R2B remains permanently **`FAILED — authorized protected acquisition attempt failed`**. Its source, policy, report, tests, authorization, invocation, response, outcome, quarantine, and namespace remain unchanged. No verified or promoted body was added there.

The audit-cleared R2B.1 response-contract identity is `sha256:3d179b91ae36ad5e8c4f0bc928496695c18c4629e2a90f557ecc1ad3ccedbbad`. Its five generated artifacts and its committed/runtime inputs re-hashed exactly.

The write-once R2B.2 authorization is 78,108 bytes with SHA-256 `a3aed05f8bbda444d52b6019227f1831e9ec466541ff3cdb9e8297a701120c8c`. It contains exactly original ordinals 2–60 and explicitly records ordinal 1 as `offline_revalidation_only` with `network_authorized=false`.

## 2. Atlanta offline revalidation

Atlanta Base remained at original request ID `teamdashlineups:1610612737:base`, ordinal 1, canonical request identity `9809de72e3a017b700ce2059a77b9ba31128cb467f2e9fde516119f6230bf64b`, and attempt 1. The original 51,905 bytes re-hashed to `e2134b18de903b79b1bcce8d628cf041ae18a50ccab00018d3b29b7daa63aff0`; canonical JSON re-hashed to `bac19c1df5f1a25de0e558c62410457917bb25ffb9130833e346444ae8c30f8d`.

The corrected contract reproduced 57 `Overall` headers and one row; 56 `Lineups` headers and 200 rows; 200 canonical pairs; zero row-width, duplicate, malformed-ID, same-player, invalid-player-ID, or required-field errors; `exact_250=false`; and Base `POSS` absent as expected. The request, returned parameters, and singleton `Overall` team identity agreed.

The R2B.2 record is `offline_revalidated_reference`. It references the original response and quarantine in place. The body was not copied or promoted. Atlanta network attempts in R2B.2: **0**. No ordinal-1 directory or transport start record exists in the R2B.2 evidence namespace.

## 3. Official invocation and timing

- Official invocation count: **1**
- Network attempt count: **59**
- Completed verified requests: **59**
- Automatic retries: **0**
- Redirects followed or accepted: **0**
- Failed/quarantined continuation identities: **0**
- Python: `C:\Users\mehan\code\hanson-hoops\.venv\Scripts\python.exe`
- Working directory: `C:\Users\mehan\code\hanson-hoops\research\pair-fit-v2`
- `PYTHONPATH`: `C:\Users\mehan\code\hanson-hoops\research\pair-fit-v2\src`
- Invocation recorded: `2026-10-02T00:48:10.388176Z` (`2026-10-01 19:48:10` CDT)
- First start: `2026-10-02T00:48:10.596285Z`
- Last outcome: `2026-10-02T00:50:34.239610Z`
- First-start-to-last-outcome wall time: 143.643325 seconds
- Sum of measured transport intervals: 85.469 seconds; range 0.250–2.984 seconds

The implementation paced by a monotonic clock, sleeping until one second after the preceding request returned. All 58 pacing waits were executed. UTC record differences from the prior outcome timestamp to the next start averaged 1.002996 seconds and ranged 0.986753–1.011286 seconds; three wall-clock deltas were 6.8–13.2 ms below one second even though the monotonic pacing path ran. This small wall-clock/monotonic discrepancy is disclosed for audit and was not repaired or rerun.

The exact official command arguments were the R2B.2 CLI `acquire` command with project root `.`, planning directory `planning\phase3f-r2b.2`, authorization `planning\phase3f-r2b.2\authorization.json`, and evidence root `cache\phase3f-r2b.2\protected-final-target`.

## 4. Ordinals 2–60

Every entry below has attempt number 1, HTTP 200, zero retries, and no redirect.

| Ordinal | Team | Measure | Attempt | HTTP | Rows | Bytes | Raw SHA-256 | Canonical JSON SHA-256 | Retries | Redirect | Disposition |
|---:|---|---|---:|---:|---:|---:|---|---|---:|---|---|
| 2 | Atlanta Hawks | Advanced | 1 | 200 | 200 | 53800 | `786e2d5b2895178c84b478c079d618ee9ea45e4c1fcb01ed36ab8a151ce35676` | `a443d7c26c660877cccc13061dffeefc57d321d0acadc355c6e78ab2aff8f0cf` | 0 | false | completed_verified |
| 3 | Boston Celtics | Base | 1 | 200 | 160 | 41641 | `638f661ab3ba9e608bd1dbe0b96b4ccf945a71a4a777fddac49dc9f861af366f` | `8d9ccb6656008e89836991215899af6e95e65586a2566b0bb9ab712171ecfb3c` | 0 | false | completed_verified |
| 4 | Boston Celtics | Advanced | 1 | 200 | 160 | 42768 | `294af64a74294e31221227a59a766d970c22c0b20df2c3b4781cac6cf97b9476` | `c34571c332891cfbdb9a3aab8e9859bcc71b369b223b6394421c297e9180c713` | 0 | false | completed_verified |
| 5 | Cleveland Cavaliers | Base | 1 | 200 | 196 | 51293 | `b555b29f6f58b768a4efbd0640adadcbc0b01bbedee00109e884af189cd1c839` | `f862c13fbe31c331273d387849b5971d359455b45674fcbb4786ae649dce4e48` | 0 | false | completed_verified |
| 6 | Cleveland Cavaliers | Advanced | 1 | 200 | 196 | 52615 | `b150c52a5f5abe67e51d8198f6ed1f22837d90dedc18636487a7e0e28bbc1eac` | `dd0327e5dbb351c42ca72d63dbef3e31f41e500ce66775bb1c5bad0bc4675fcb` | 0 | false | completed_verified |
| 7 | New Orleans Pelicans | Base | 1 | 200 | 147 | 38775 | `9fba8d8e8801f84a0aee758b8f70ba73cab0cd1384c657aac18528fd4be1b8f3` | `c470b2377ef86343055ce0a1dad0e44d71db1a869c154f421aa0bc1c6256012a` | 0 | false | completed_verified |
| 8 | New Orleans Pelicans | Advanced | 1 | 200 | 147 | 39693 | `5bc693837c57ff9b006fe230e4eee5119125caafb5d90d45731f0dd461dcdd63` | `5ca1514532aae17e2a1f9068cf2844b1a2f8c076a3fe98d76415dbf42ff98bbe` | 0 | false | completed_verified |
| 9 | Chicago Bulls | Base | 1 | 200 | 238 | 62036 | `ce9eedfa244f8367568a0353c1bf28b399ee3ac8e3bb8fd4d42f1c139943ca1a` | `a3347100bbde52ef43e3ef0f9c12a89c9fdc0a8a90a6dad1cc1746584cd4dd3e` | 0 | false | completed_verified |
| 10 | Chicago Bulls | Advanced | 1 | 200 | 238 | 63972 | `e8a706693996e4214683ff7d8e6c14813d02312621d9b5e415c2b8de66d6150e` | `1e7a2f76ddcad7e877b455b9f3fe069df1e1da316807765cf9253bc91dd0639b` | 0 | false | completed_verified |
| 11 | Dallas Mavericks | Base | 1 | 200 | 206 | 54334 | `8822b57d6b05c85b2ef3513de4fb7eb743bbae2aa681b3a2962d2fb7f415060f` | `2b6db8d917f1e6df579369ccc834e4d3fc0b69ab2a35ef6b1912a3d2cf934aa9` | 0 | false | completed_verified |
| 12 | Dallas Mavericks | Advanced | 1 | 200 | 206 | 55763 | `a90660c9f8305bafbb54d92e9dde95db5d8d4ff60ca128343d3bce4a696f9c43` | `58c78d3d3aaf94e94f5818e6456a7d8d9091ae7ab1a23d4e461f049ccf04090e` | 0 | false | completed_verified |
| 13 | Denver Nuggets | Base | 1 | 200 | 156 | 40489 | `f744739e99a29d1bfb1717111fba665068f6ad1a86eb90718ccd1fbddf8ff7a0` | `b922e7bacb49d56917d67abed1c05aeaa12f76cf41d3d3d2c3aa39336139a96a` | 0 | false | completed_verified |
| 14 | Denver Nuggets | Advanced | 1 | 200 | 156 | 41695 | `2701c99ba344788aaf52b0a08152a107bd7bde6a05da48d7c749c66ba30f4952` | `8604fc07f8ff8f82b3b80280ea1d71e1f4f9f25a98c211cb71dd740cdfd197e0` | 0 | false | completed_verified |
| 15 | Golden State Warriors | Base | 1 | 200 | 199 | 52516 | `a6f85de09933fde6a34fc75e15180432f5ceb70dc3aeef5be2d8d759bb799786` | `606f76aff2382dd39e73e6601d942e385462035100f0112ed66950ce194cf474` | 0 | false | completed_verified |
| 16 | Golden State Warriors | Advanced | 1 | 200 | 199 | 53809 | `f4e1bd3a8e9b99249a5a8bfa05c3e1d931a0b3a81a65b9928b9a414ca67f09ec` | `ee2eabe3ae4b3b7a59f02ba44d6c1162f47f9c24bffa6250e2bfab6a19135e8e` | 0 | false | completed_verified |
| 17 | Houston Rockets | Base | 1 | 200 | 110 | 28796 | `6520ec2341c5c81ec6167dfa349959f379f21db88f021b7e25dc7a0d17753b21` | `585fd12331ecb3303af6d23cd1a54d76eb8708f44cf6c54a56b63cdd313bb2cf` | 0 | false | completed_verified |
| 18 | Houston Rockets | Advanced | 1 | 200 | 110 | 29550 | `ef615942ecfd627ec34e5df28b3d1bedd9b57c7b464eb638a5a66d4b8bacc51e` | `9699e615940ad1b4bf46a30a6b13a958311d590368b56d4d00ef460f51734187` | 0 | false | completed_verified |
| 19 | LA Clippers | Base | 1 | 200 | 205 | 53245 | `d2e54f6de9ae782e6a4b5224a12723723263341303d05023908b2807460ae86b` | `8562c1b92077a97a2ece9e184ffd35d3a50da19b0178177cf55b45cead446065` | 0 | false | completed_verified |
| 20 | LA Clippers | Advanced | 1 | 200 | 205 | 54759 | `8c6797c94f8a02d07fb6009abfdfbdfb0ae111494cd16aa3d8ea8e473043477f` | `832ffa73738edade0cb054e4eea5c8698e0deff70dea28528eacf1e2f2ca9226` | 0 | false | completed_verified |
| 21 | Los Angeles Lakers | Base | 1 | 200 | 168 | 43775 | `0598ee9c02943b74e0061daa3a21387777ea44f46556b807228a889c39696e5d` | `260f5fc7d018789f795faf7ded764db8f50623ad3ab78d960f71eed3648d26a4` | 0 | false | completed_verified |
| 22 | Los Angeles Lakers | Advanced | 1 | 200 | 168 | 45123 | `570d86bf2ee45e102ede8d858d2ecf0cc85970dffed89a72af07a54624f439f9` | `ef84c869fc4398f8278458779edb8888af26c1150a09e92a2612dc883609c48a` | 0 | false | completed_verified |
| 23 | Miami Heat | Base | 1 | 200 | 116 | 30684 | `8ccfa4ed9383b332b09f0ab7acb94f7c26d2c27d4d7c8e867267b2a5a3fca8bf` | `ea1ac50d3a2c3a0eaab0967cdbee390a1327f6872c79cf37b7e526615478ced2` | 0 | false | completed_verified |
| 24 | Miami Heat | Advanced | 1 | 200 | 116 | 31466 | `8be13d59397fc48a47f5114d305ec67b77673df046a19b8c76f2acfff111e425` | `aefd490ace04069baa61186d2042cbb09594e1fad519ea985b1ccf56dc498115` | 0 | false | completed_verified |
| 25 | Milwaukee Bucks | Base | 1 | 200 | 178 | 46830 | `475a3ed005c1784d2b5eea40853567308be0e026529ef307b6445df39ce41253` | `d1bf3f78a05f4aa210e5cf85b3577df0f68ad6696e9cfed43a93f65877e2c5df` | 0 | false | completed_verified |
| 26 | Milwaukee Bucks | Advanced | 1 | 200 | 178 | 48093 | `0fd0ec0925bef2e2c117a60a203191f9b0fe85104a8dbc01da2b447992c3d806` | `1fa91cab9c68273d15ded6d2ea2fc4ee70f01c073196ddc0ccfa2b601a4a7be8` | 0 | false | completed_verified |
| 27 | Minnesota Timberwolves | Base | 1 | 200 | 160 | 41572 | `b8923a5440c68fb50731e055d1558f7b030a142ad59a724921bbaeee713c2f3d` | `18dc138328f2e881b074bed41ada173d8a750c4721a4f7342fc1bc10c0a1d7a2` | 0 | false | completed_verified |
| 28 | Minnesota Timberwolves | Advanced | 1 | 200 | 160 | 43055 | `e1b3ed49213c4460252685f16db6909de9989623a945b86495a6597de7464ae5` | `e35322d89f79c686e633487bfe04d468ac81d9edd3204a8d470b29499ba015fa` | 0 | false | completed_verified |
| 29 | Brooklyn Nets | Base | 1 | 200 | 195 | 51095 | `b70ef43e8c987f98b7f96cf8d17c12c3f63a31c0872e395166ff7504e54b47f1` | `2171e82e07a04fb7b2626820ef9d449f1dfa3aab303017ffc8c8eba010b83ed9` | 0 | false | completed_verified |
| 30 | Brooklyn Nets | Advanced | 1 | 200 | 195 | 52330 | `9af2bcb4dc054d3f0467c043dd154a694b73b1e9f11151859f59b0f4c01aa3ad` | `4182e6de48119c8956127083f527defb7deed2a0517fdf2cb3a7bb1fc7036c8c` | 0 | false | completed_verified |
| 31 | New York Knicks | Base | 1 | 200 | 166 | 43343 | `dcc1671881d64d6c58124d7d740d7c16543eb19557e0af09f2a8356b3674cae6` | `2687f545ff5ec93712d62e540a9ea689ec676e9b02ddce92ceb9483d42a0f454` | 0 | false | completed_verified |
| 32 | New York Knicks | Advanced | 1 | 200 | 166 | 44631 | `37d695d336de5f793d99e78604cb9b72fd3c95b29f7a5927685c37af586b947d` | `26bdd3ff42f0eaca140ac7daff7742ed82707b863be3f695dc701f8ed05215b1` | 0 | false | completed_verified |
| 33 | Orlando Magic | Base | 1 | 200 | 139 | 36801 | `44e6bc2620aa57a099a33a6a004160258a7331654c4f21bc6d60f8eca0639bac` | `faed7d74d0b4264250e070903b6554dfaf19c2b2efadd6d99b3341034cbe2d17` | 0 | false | completed_verified |
| 34 | Orlando Magic | Advanced | 1 | 200 | 139 | 37565 | `0ad413e49a5ed85c52f9d8f27dd3c8c496cc68cb11fa55ffea6dddeb94a37707` | `af3529bf7fc87fabdf3c354158973cbe57cb39e3adbb93969edbca5356931201` | 0 | false | completed_verified |
| 35 | Indiana Pacers | Base | 1 | 200 | 250 | 65800 | `d0ec683e2879e8e58022114935b248f62531f88248c1e6a1374abca6def76bc3` | `0d55c4152259849055742855c5a156db935a2e12e77435a2b7b13d382ec945a5` | 0 | false | exact_250_unresolved |
| 36 | Indiana Pacers | Advanced | 1 | 200 | 250 | 67740 | `45d6bf8a6fd7e1dcc1b47c5f3b52c278a1e0a8830a80a1a6b01d70e8e1a8faee` | `605e83bb954be19b6b52a29822c3dd6bfaf4f33e7fb5b483b61625aab1871120` | 0 | false | exact_250_unresolved |
| 37 | Philadelphia 76ers | Base | 1 | 200 | 193 | 49758 | `588f2db4dc9a8ebe0bf9be3de2a860e107988c0ccf9c2a1bf4c05484872a0b7e` | `7033906f1223cde92fe015f769f4c2857c4f436c9775eb382ed9a243e9c2bb36` | 0 | false | completed_verified |
| 38 | Philadelphia 76ers | Advanced | 1 | 200 | 193 | 51449 | `96fe49a90078cf8f7efcdac9fb090f94fd48ad9a8d2d3a395a87769511a16494` | `105e434c1c131aac6ff86225aab64f777257ca15f4f02c50b2e35e504a460763` | 0 | false | completed_verified |
| 39 | Phoenix Suns | Base | 1 | 200 | 163 | 42802 | `2682baaad530c72bfb292936038b1c5b28b72f0f066c10b6045ca17690e02e56` | `a87743d2fd1f38de227121bb173dafd1321c6fc4264f9a6b01c28519d707f0ed` | 0 | false | completed_verified |
| 40 | Phoenix Suns | Advanced | 1 | 200 | 163 | 43901 | `7b0acbea749407b5fbb2068bf882372f9e9034e1e3009cb83afe228ccc195555` | `8dcc3ed54d8e9055bc781a2461c6e24c75448fc56be642b737529d27657a7659` | 0 | false | completed_verified |
| 41 | Portland Trail Blazers | Base | 1 | 200 | 162 | 42448 | `ab7ede59ddb4151d4d3c88b78c3631da040bf70b6a68f33b0720fd668822be6e` | `64e587da69eb3db240e043af9f50fc18e0bbad5171afcab049b72420e7cf9450` | 0 | false | completed_verified |
| 42 | Portland Trail Blazers | Advanced | 1 | 200 | 162 | 43533 | `e9830aed061ebd9c2f6d8121377f8f28a7100ed6622a5d63887880d456fdf410` | `454ed64dc11d17203033d33189459dae5783ce41694658d0a00b97afbee224da` | 0 | false | completed_verified |
| 43 | Sacramento Kings | Base | 1 | 200 | 190 | 49653 | `4f9bbfe9ff3c8e61b16d3b9dab17d9fc637254e73a918837199a766ea1c4c83f` | `eebef42a36bef61f1f966d58a95ccecd9646b44820ce7d4e622ae1fb539af1e3` | 0 | false | completed_verified |
| 44 | Sacramento Kings | Advanced | 1 | 200 | 190 | 51135 | `52ebe5b34b36ec2151947046def2bda42edee639ebd5c661bff4fb5a8f33086d` | `7ecae4cfb978d183ad866736619c338785e8af89bbe438e6440a58102291d2c6` | 0 | false | completed_verified |
| 45 | San Antonio Spurs | Base | 1 | 200 | 144 | 37587 | `a4d7dd68ba619d88ca3eaeca75c3ae71006f334ffe5fc706231ea05454c5b73a` | `ce6733fea52b2ebb627599a7ee2a96d664c4651153e50fe1c634e27aecc32f4e` | 0 | false | completed_verified |
| 46 | San Antonio Spurs | Advanced | 1 | 200 | 144 | 38878 | `ff3b134bde4c23eddfd68aef7c4a08e7a3d42013c06991e93e4efe481205a6e9` | `60fc241b39734688e055b535c585429bc6c840b3031562798d1f3affc8d413f0` | 0 | false | completed_verified |
| 47 | Oklahoma City Thunder | Base | 1 | 200 | 159 | 42281 | `581c28cc77cecc54cf14149b6e19f3c3eb61cd48a2ca2b9802deb74ea9a5b4ac` | `1edee7cbdc5755ee7b548ebc4353e66e95e6a1074e19f0667da37e3cc6138010` | 0 | false | completed_verified |
| 48 | Oklahoma City Thunder | Advanced | 1 | 200 | 159 | 43235 | `61c84c9305cd7935291d4588dfdcc3c3c074283e864bc6373152f31b4c596941` | `7ed79e9d2fe9e8db29099fb9a9f1bc0f635c8da922d8e47acb1d09c8fcd2e90a` | 0 | false | completed_verified |
| 49 | Toronto Raptors | Base | 1 | 200 | 165 | 42654 | `1fbf0b311dc9bd40266dac7cb12ebec1a89e0f1703c2d86fb120be8a571cd519` | `73f5c1b39d46ca7dcd1efae35c4eddf32f002a4c90a610c05698849f9d358905` | 0 | false | completed_verified |
| 50 | Toronto Raptors | Advanced | 1 | 200 | 165 | 44182 | `dc32648921713e1f0868e46c0482e1ae4b15517f8319f637bac4e4aeb7714885` | `970804331c87a2fada1692526d8fd7e34db6378b3c71babecafb2488cfae4035` | 0 | false | completed_verified |
| 51 | Utah Jazz | Base | 1 | 200 | 209 | 55239 | `1dd4d4ac9f7de5885266d8caf82be950bf685452fd239e6e4ccf16bc55bfbab5` | `8b5680d84329bc8b9d25f42925e5cd5b470f11a5d9d2275dd0da76be5c4a583f` | 0 | false | completed_verified |
| 52 | Utah Jazz | Advanced | 1 | 200 | 209 | 56788 | `6233445e5c8dfb3a6ec9b512b592ed5da903910767c153af7252d504996f39d6` | `bbef9e069d7b4f15fe724622441c35014e42418f8a1e95e640b7ce3e734b3b22` | 0 | false | completed_verified |
| 53 | Memphis Grizzlies | Base | 1 | 200 | 250 | 66452 | `540373cff09b3b5027144ef28a750a412408b23a01c56c7af256e309e2600b29` | `b562a30a8b188d73c6a66e5cd0851f028c0e1619245c01bb7fceb54d066eeccc` | 0 | false | exact_250_unresolved |
| 54 | Memphis Grizzlies | Advanced | 1 | 200 | 250 | 68221 | `d7d59969325bc6731c057c7035f6629d2d28e079b6256c2fe87e83a386301fc6` | `2a7937fc2a54f855b39fa2cd92df1035c8ad9072bb2b8ab4b3ebcccccc4edfa3` | 0 | false | exact_250_unresolved |
| 55 | Washington Wizards | Base | 1 | 200 | 228 | 59811 | `bd26603a22728f0cd88fca2b6ae035a818645ee09401f7e4f8be7f89dc30603a` | `5fc38798ac2a3cf9f6bd1ce950e6f2f41246eb9fa6328218bff543bda3ec3d19` | 0 | false | completed_verified |
| 56 | Washington Wizards | Advanced | 1 | 200 | 228 | 61663 | `e78c06ec4c2e6fdbf54956027dcb2f1f07beb1a1d2fbbdd0f44d31485edfe9d3` | `1e047c22714a4c53a1ab451d610ee5ca33759c7b8c6e9b911d40f026a48f9210` | 0 | false | completed_verified |
| 57 | Detroit Pistons | Base | 1 | 200 | 163 | 42426 | `bcc11a76f78fb0ae5c60657065aee66c0d249f9d03d48ad3fe03881b9c2d18f6` | `95a7e677657c8f548c26daad6780b58ff30f125876dde9c16539799025f99519` | 0 | false | completed_verified |
| 58 | Detroit Pistons | Advanced | 1 | 200 | 163 | 43621 | `94bbf55bf25adbc23acaee7695cc445ac998d9fa2e8bce6887f6318d1b4a5612` | `ab10c5166cf606ac36ae23138f70e2f567b64044150a95b6d4ff4db8773c4e63` | 0 | false | completed_verified |
| 59 | Charlotte Hornets | Base | 1 | 200 | 188 | 48972 | `c6c85fb047d89b251448042758e503413a63db9ae96c4687a14d29acc53022b2` | `d64cd7781ddab7a490866430ed1ba09ba011756fec3f3b6c3657ec6e25cceeb3` | 0 | false | completed_verified |
| 60 | Charlotte Hornets | Advanced | 1 | 200 | 188 | 50390 | `6559887f9f9bf60f4885860c86df7afc50805a8e1660d049734de44bb83ce0fe` | `7a170111f89d34f3ec74e7e941415bcdf2d072d5462480899d6a01251d7cd801` | 0 | false | completed_verified |

## 5. Thirty-team Base/Advanced reconciliation

`Base/Advanced rows` and `Base/Advanced keys` are equal for every team. `Only` is Base-only/Advanced-only key count. `Zero/exact` is Advanced zero-possession rows and whether either response has exactly 250 rows.

| Team | Team ID | Base/Advanced rows | Base/Advanced keys | Intersection | Only | Invalid | Zero/exact | Disposition |
|---|---|---:|---:|---:|---:|---:|---|---|
| Atlanta Hawks | 1610612737 | 200/200 | 200/200 | 200 | 0/0 | 0 | 1/false | structurally_complete_non_250 |
| Boston Celtics | 1610612738 | 160/160 | 160/160 | 160 | 0/0 | 0 | 0/false | structurally_complete_non_250 |
| Cleveland Cavaliers | 1610612739 | 196/196 | 196/196 | 196 | 0/0 | 0 | 0/false | structurally_complete_non_250 |
| New Orleans Pelicans | 1610612740 | 147/147 | 147/147 | 147 | 0/0 | 0 | 0/false | structurally_complete_non_250 |
| Chicago Bulls | 1610612741 | 238/238 | 238/238 | 238 | 0/0 | 0 | 1/false | structurally_complete_non_250 |
| Dallas Mavericks | 1610612742 | 206/206 | 206/206 | 206 | 0/0 | 0 | 1/false | structurally_complete_non_250 |
| Denver Nuggets | 1610612743 | 156/156 | 156/156 | 156 | 0/0 | 0 | 2/false | structurally_complete_non_250 |
| Golden State Warriors | 1610612744 | 199/199 | 199/199 | 199 | 0/0 | 0 | 0/false | structurally_complete_non_250 |
| Houston Rockets | 1610612745 | 110/110 | 110/110 | 110 | 0/0 | 0 | 0/false | structurally_complete_non_250 |
| LA Clippers | 1610612746 | 205/205 | 205/205 | 205 | 0/0 | 0 | 0/false | structurally_complete_non_250 |
| Los Angeles Lakers | 1610612747 | 168/168 | 168/168 | 168 | 0/0 | 0 | 0/false | structurally_complete_non_250 |
| Miami Heat | 1610612748 | 116/116 | 116/116 | 116 | 0/0 | 0 | 0/false | structurally_complete_non_250 |
| Milwaukee Bucks | 1610612749 | 178/178 | 178/178 | 178 | 0/0 | 0 | 1/false | structurally_complete_non_250 |
| Minnesota Timberwolves | 1610612750 | 160/160 | 160/160 | 160 | 0/0 | 0 | 0/false | structurally_complete_non_250 |
| Brooklyn Nets | 1610612751 | 195/195 | 195/195 | 195 | 0/0 | 0 | 0/false | structurally_complete_non_250 |
| New York Knicks | 1610612752 | 166/166 | 166/166 | 166 | 0/0 | 0 | 0/false | structurally_complete_non_250 |
| Orlando Magic | 1610612753 | 139/139 | 139/139 | 139 | 0/0 | 0 | 0/false | structurally_complete_non_250 |
| Indiana Pacers | 1610612754 | 250/250 | 250/250 | 250 | 0/0 | 0 | 0/true | exact_250_unresolved |
| Philadelphia 76ers | 1610612755 | 193/193 | 193/193 | 193 | 0/0 | 0 | 0/false | structurally_complete_non_250 |
| Phoenix Suns | 1610612756 | 163/163 | 163/163 | 163 | 0/0 | 0 | 1/false | structurally_complete_non_250 |
| Portland Trail Blazers | 1610612757 | 162/162 | 162/162 | 162 | 0/0 | 0 | 0/false | structurally_complete_non_250 |
| Sacramento Kings | 1610612758 | 190/190 | 190/190 | 190 | 0/0 | 0 | 1/false | structurally_complete_non_250 |
| San Antonio Spurs | 1610612759 | 144/144 | 144/144 | 144 | 0/0 | 0 | 0/false | structurally_complete_non_250 |
| Oklahoma City Thunder | 1610612760 | 159/159 | 159/159 | 159 | 0/0 | 0 | 0/false | structurally_complete_non_250 |
| Toronto Raptors | 1610612761 | 165/165 | 165/165 | 165 | 0/0 | 0 | 0/false | structurally_complete_non_250 |
| Utah Jazz | 1610612762 | 209/209 | 209/209 | 209 | 0/0 | 0 | 1/false | structurally_complete_non_250 |
| Memphis Grizzlies | 1610612763 | 250/250 | 250/250 | 250 | 0/0 | 0 | 0/true | exact_250_unresolved |
| Washington Wizards | 1610612764 | 228/228 | 228/228 | 228 | 0/0 | 0 | 1/false | structurally_complete_non_250 |
| Detroit Pistons | 1610612765 | 163/163 | 163/163 | 163 | 0/0 | 0 | 0/false | structurally_complete_non_250 |
| Charlotte Hornets | 1610612766 | 188/188 | 188/188 | 188 | 0/0 | 0 | 0/false | structurally_complete_non_250 |

Atlanta Base’s source is the original R2B offline reference. Every other Base response and all 30 Advanced responses are from R2B.2. All 30 Base/Advanced canonical key sets are equal. No team has a row-count or key mismatch, invalid pair identity, invalid required field, duplicate pair, or malformed pair.

## 6. Global structural findings

- Original protected identities: 60
- Offline-revalidated identities: 1
- New completed verified requests: 59
- Available Base responses: 30
- Available Advanced responses: 30
- Raw Base rows: 5,403
- Raw Advanced rows: 5,403
- Unique team × canonical-pair population: 5,403
- Structurally complete non-250 teams: 28
- Exact-250 unresolved teams: 2
- Base/Advanced mismatch teams: 0
- Invalid-pair teams: 0
- Invalid-field teams: 0
- Advanced zero-possession rows: 10, retained in evidence
- Duplicate canonical pairs: 0
- Malformed pairs: 0
- Failed or quarantined continuation identities: 0

Indiana’s triggers are ordinals 35 and 36. Memphis’s triggers are ordinals 53 and 54. Each team has 250 equal Base/Advanced canonical keys, but exact-250 does not prove exhaustiveness. Both remain `exact_250_unresolved`; neither was automatically excluded, truncated, or selectively retained. Recovery requires a later separate policy and authorization.

## 7. Generated evidence and deterministic replay

The ignored planning namespace contains exactly 14 files:

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `authorization.json` | 78,108 | `a3aed05f8bbda444d52b6019227f1831e9ec466541ff3cdb9e8297a701120c8c` |
| `official_invocation.json` | 1,052 | `bd284af99c0baa837d79843113d45df48ce0f6baba27cb14839a5304a43a1a81` |
| `atlanta_offline_revalidation.json` | 2,314 | `18333d79b079005cb9d4951ad2c1a976c426f4d9f9c554d3c87214c66263be86` |
| `request_inventory.json` | 58,173 | `0f974738708aa78160d75826cc34c54ba5caa0cf4f78c51f8aa71301b69fe00b` |
| `attempt_inventory.json` | 100,569 | `e007784a92958d1155dc88e146d0375a2c85f64fc6fb5b21d3cf83a8259b9a10` |
| `response_verifications.json` | 668,760 | `38ebee18d62c26516d120d51bc4a63bd02053cf5da5718c8618b7a297dee1b3d` |
| `response_fingerprints.json` | 17,334 | `bcee8a66c142f33ab77cc092eca2618e24a2af8e7a6942925e486204f69c5ec2` |
| `team_reconciliation.json` | 25,504 | `46f6413aff956bcf40d857d68f518df0133c56dca1b23861255586882e6fd936` |
| `global_reconciliation.json` | 1,069 | `d13133806d08893989cc19ccf85d78dea0a4f784b939b376de0859f6eff3474c` |
| `exact_250_inventory.json` | 1,824 | `ea183ad78133e22aee99be371107a3296d814385b9887cea3dbe6b2773e3ae97` |
| `structural_dispositions.json` | 3,652 | `3e771861882d4c413c6b1a42cb1501e447456ed5f8e2f66bbe5de485dd28a922` |
| `input_fingerprints.json` | 9,506 | `9eb3efee8ff924e3e275fe5f25bd2cb5d02c1d3325f7e71d58386a47e4440931` |
| `summary.json` | 904 | `00523960b2ce0f0f5c8431b04d96c1678f2376ee19ffc1b455a8cd41b04e0657` |
| `artifact_hashes.json` | 1,926 | `257651c2a5fe49ba292542862eb757b1ed5551d7a05542053a10d2a49da8a7d4` |

The evidence namespace contains exactly 59 ordinal-preserving identity directories. Each contains start, raw response, verification, promoted verified body, and outcome records. Read-only replay re-hashed and revalidated all 59 bodies, reproduced all 30 team records and the global reconciliation byte-for-value, verified every manifest hash, revalidated Atlanta from its original path, and confirmed the absence of ordinal 1 in R2B.2.

## 8. Tests and checks

- Focused R2B.2 suite: 23 passed before execution; 24 passed in the final expanded suite, including explicit Base/Advanced mismatch and deterministic-replay tests.
- Applicable historical regression selection: 409 passed. Four historical phase-lock assertions failed only because they require obsolete committed HEADs: one R0.1 Git-state assertion and three R2B.1 build assertions.
- R0.1 remainder with its obsolete-HEAD assertion deselected: 23 passed, 1 deselected.
- R2B.1 remainder with its three obsolete-HEAD build assertions deselected: 14 passed, 3 deselected.
- Historical coverage included Phase 1/2 acquisition and schemas, canonical-pair behavior, Phase 3A population, Phase 3B eligibility/target curation, Phase 3E incomplete-team handling, R0/R0.1, R1S, R2A, failed-R2B preservation, R2B.1, and R2B.2.
- `py_compile`: passed for implementation, CLI, and focused tests.
- Import-only canary: passed immediately before official execution.
- `git diff --check`: passed.
- Narrow ignore checks: passed for both new namespaces.
- Credential scan: no credential value or secret found.
- Prohibited-artifact/capability scan: no final-test table, estimator, prediction, metric, model serialization, pandas, NumPy, scikit-learn, joblib, or pickle path in the R2B.2 implementation.
- Disposable `.t` pytest paths: removed before official execution.
- Post-execution read-only replay: passed for 59 states, 13 manifest-listed non-self artifacts, 59 evidence directories, reconciliation, Atlanta offline identity, and preservation of all inherited inputs.

Pytest emitted only cache warnings because the existing `.pytest_cache` location was not writable; the explicit short basetemp paths handled test artifacts and were removed.

## 9. Explicit phase-boundary confirmations

- Atlanta network request: none.
- Unauthorized protected request: none.
- Retry: none.
- Redirect: none.
- Recovery window or date-split request: none.
- Four Factors, Usage, standings, control, alternate-season, alternate-endpoint, or player-profile request: none.
- Final-test modeling table: not constructed.
- `POSS >= 150` model population: not materialized.
- Prior-profile join: none.
- Imputation, scaling, or preprocessing fit: none.
- Estimator load or fit: none.
- Prediction, residual, calibration, subgroup error, MAE, RMSE, R², correlation, bias, target distribution, target mean, or baseline calculation: none.
- Model artifact or serialization: none.
- All six final-test readiness gates: pending.

## 10. Interpretation and next step

What the evidence proves: Atlanta’s original bytes satisfy the corrected Base contract; all 59 authorized continuation responses are immutable, strict-contract-verified HTTP 200 evidence; all 30 Base/Advanced key sets match; and only Indiana and Memphis trigger exact-250 uncertainty. It also proves no acquisition failure, pair defect, field defect, or Base/Advanced mismatch in the available evidence.

What the evidence suggests: the 28 non-250 teams are structurally complete under the frozen full-season response contract. Indiana and Memphis may also be complete, but an exact 250-row response alone cannot establish that.

What remains a user decision: whether to authorize a separate checkpoint for Indiana and Memphis and, after that checkpoint is audited, how to resolve final-test readiness. No such decision is made here.

What requires read-only audit: the authorization boundary; original-R2B preservation; the disclosed monotonic/UTC pacing discrepancy; all response fingerprints and restart states; Indiana/Memphis exact-250 triggers; 30-team key equality; the deterministic replay; and the 14 generated artifacts.

What remains unauthorized: any recovery request, complementary date window, dataset construction, profile join, preprocessing, model execution, prediction, metric, performance interpretation, or final scientific classification.

The narrowest justified next step is a **read-only audit of Phase 3F-R2B.2**, with special attention to the two exact-250 teams and the disclosed pacing timestamps. Stop there; do not authorize recovery or modeling as part of that audit.
