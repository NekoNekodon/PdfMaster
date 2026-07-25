rule PDF_DANGER_SCRIPT
{
    meta:
        desc = "检测PDF自动执行、JS脚本风险"
    strings:
        $oa = "/OpenAction"
        $js1 = "/JavaScript"
        $js2 = "/JS"
        $aa = "/AA"
    condition:
        any of ($*)
}