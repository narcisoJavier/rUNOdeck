using System;
using System.Runtime.InteropServices;
using Microsoft.Win32;

public enum ERole : uint {
    eConsole = 0,
    eMultimedia = 1,
    eCommunications = 2,
    ERole_enum_count = 3
}

[ComImport]
[Guid("870af99c-171d-4f9e-af0d-e63df40c2bc9")]
class CPolicyConfigClient {}

[ComImport]
[InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
[Guid("f8679f50-850a-41cf-9c72-430f290290c8")]
internal interface IPolicyConfig {
    // Methods 3 to 12: Placeholders to align the vtable offset for Windows 10/11
    [PreserveSig] int Method3();
    [PreserveSig] int Method4();
    [PreserveSig] int Method5();
    [PreserveSig] int Method6();
    [PreserveSig] int Method7();
    [PreserveSig] int Method8();
    [PreserveSig] int Method9();
    [PreserveSig] int Method10();
    [PreserveSig] int Method11();
    [PreserveSig] int Method12();

    // Slot 13: SetDefaultEndpoint
    [PreserveSig]
    int SetDefaultEndpoint(
        [MarshalAs(UnmanagedType.LPWStr)] string wszDeviceId, 
        ERole eRole
    );
}

public class Program {
    public static int Main(string[] args) {
        if (args.Length == 0) {
            Console.WriteLine("Usage: SetAudioDevice.exe <keyword>");
            return 1;
        }

        string keyword = args[0].ToLower();
        string matchedId = null;
        string matchedName = null;

        string renderPath = @"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render";
        using (RegistryKey hkey = Registry.LocalMachine.OpenSubKey(renderPath)) {
            if (hkey != null) {
                foreach (string guid in hkey.GetSubKeyNames()) {
                    try {
                        using (RegistryKey devKey = hkey.OpenSubKey(guid)) {
                            object stateObj = devKey.GetValue("DeviceState");
                            if (stateObj != null && (int)stateObj == 1) { // 1 = Active
                                using (RegistryKey propKey = devKey.OpenSubKey("Properties")) {
                                    if (propKey != null) {
                                        object nameObj = propKey.GetValue("{a45c254e-df1c-4efd-8020-67d146a850e0},2");
                                        if (nameObj != null) {
                                            string name = nameObj.ToString();
                                            if (name.ToLower().Contains(keyword)) {
                                                matchedId = "{0.0.0.00000000}." + guid;
                                                matchedName = name;
                                                break;
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    } catch {}
                }
            }
        }

        if (matchedId == null) {
            Console.WriteLine("No active audio device found matching: " + keyword);
            return 1;
        }

        try {
            IPolicyConfig policyConfig = (IPolicyConfig)new CPolicyConfigClient();
            Marshal.ThrowExceptionForHR(policyConfig.SetDefaultEndpoint(matchedId, ERole.eConsole));
            Marshal.ThrowExceptionForHR(policyConfig.SetDefaultEndpoint(matchedId, ERole.eMultimedia));
            Marshal.ThrowExceptionForHR(policyConfig.SetDefaultEndpoint(matchedId, ERole.eCommunications));
            Console.WriteLine("Successfully switched audio to: " + matchedName);
            return 0;
        } catch (Exception ex) {
            Console.WriteLine("Error switching audio: " + ex.Message);
            return 1;
        }
    }
}
