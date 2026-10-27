# HyperOS 4.0 on Galaxy S24 Ultra (e3q)

This is an in-progress runtime port. The profile at
`profiles/e3q-hyperos4.json` is not launch permission; `launch_enabled` remains
false.

## Identified inputs

- Host: Samsung Galaxy S24 Ultra, SM-S928B / e3q / SM8650, Android 17 / SDK 37,
  One UI 9, build `S928BXXU6EZIF`.
- Host `services.jar` SHA-256:
  `665a78975a3c63668e308ba3dc64c1f4e37eeaf4f271af2ff97db7b6aafba7f2`.
- Host `framework.jar` SHA-256:
  `4e2eaa64e3b5786a3680b4167d1a39fbfbca4675d15e132fe167b9015718cb60`.
- Host ART `service-art.jar` SHA-256:
  `4e1229e8582ea6f03d7f9264fa07a3f3bef02e2ffd74d6ab93a4df16ae19c66c`.
- Guest: raw ext4 `hyperosS24Ultra.img`, 6,392,864,768 bytes, SHA-256
  `ba016df72abf030c9e1d4d993a1aef23f6c4923538dd89e3de71c401b634518b`.
- Guest build: HyperOS 4.0 / Android 17 / SDK 37,
  `17OS4.0.260809.221254686.QCPECN.S`.
- Thirty-four guest APEX payloads were extracted from the exact image. A
  matching 85-method host `IInstalld` table was derived from the captured host
  `services.jar`. These preparation inputs are local and are not release
  runtime binaries.
- The guest ART `service-art.jar` SHA-256 is
  `8cfcac48fe06c48aea7a020c145ce5a3cc0f10d22a67e8573fe3907a6ae28ab4`.
  An offline ART adapter candidate was assembled for the exact host/guest pair
  (SHA-256 `329be51948fc18e45836082dee830d08fe079b032a1a1292d6928c69e6ef45ab`).
  It matches 19 inspected parcel writers and adapts the S24 host's
  `imageLocationDebugString` field. It has not been exercised on the phone.

## Safety and remaining work

Preparation only read the guest image and host system files. It did not write
to ABL, system, vendor, ODM, system_ext, or any other phone partition. No guest
session was started.

The OneOS source provides relevant Android 17 Samsung porting references, but
its repository has no HyperOS build outputs. OneOS release profiles target
different guest systems; they do not make this HyperOS image compatible. Its
NOTICE also limits reuse of the OneLineage-derived session scripts, so this
port must use gsionlocked-owned session/runtime code.

Before launch, this port still needs HyperOS-specific framework and native
guard candidates built for the exact guest image, runtime/package integration,
and e3q-specific display, input, isolation, failure-return, and recovery
validation. No successful S24 Ultra HyperOS boot is claimed.
