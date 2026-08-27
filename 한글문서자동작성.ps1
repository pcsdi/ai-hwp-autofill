
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

[System.Windows.Forms.Application]::EnableVisualStyles()

$script:BaseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$script:SettingsPath = Join-Path $script:BaseDir "설정.json"

function Load-Settings {
    if (Test-Path $script:SettingsPath) {
        try { return Get-Content $script:SettingsPath -Raw -Encoding UTF8 | ConvertFrom-Json } catch {}
    }
    return [pscustomobject]@{ hwpExe = "" }
}

function Save-Settings($hwpExe) {
    @{ hwpExe = $hwpExe } | ConvertTo-Json | Set-Content $script:SettingsPath -Encoding UTF8
}

function Run-Hwp([string[]]$Args) {
    $exe = $txtHwpExe.Text.Trim()
    if (-not (Test-Path $exe)) { throw "hwp.exe 경로가 올바르지 않습니다." }

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $exe
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    foreach ($a in $Args) { [void]$psi.ArgumentList.Add($a) }

    $p = [System.Diagnostics.Process]::Start($psi)
    $stdout = $p.StandardOutput.ReadToEnd()
    $stderr = $p.StandardError.ReadToEnd()
    $p.WaitForExit()
    if ($p.ExitCode -ne 0) {
        throw "hwp 실행 오류`r`n$stderr"
    }
    return $stdout
}

function Normalize([string]$s) {
    if ($null -eq $s) { return "" }
    return ($s -replace '[\s:：()（）\[\]{}\-_/.,·]', '').ToLower()
}

$aliases = @{
    "프로그램명" = @("프로그램명","교육명","강의명","과정명","사업명","행사명","주제")
    "일시" = @("일시","교육일","교육일시","강의일","강의일시","날짜","운영일","일자")
    "장소" = @("장소","교육장소","강의장소","위치","개최장소")
    "대상" = @("대상","교육대상","참여대상","참가대상","수강대상")
    "인원" = @("인원","교육인원","참여인원","참가자수","참석자수","수강인원")
    "내용" = @("내용","강의내용","교육내용","주요내용","세부내용","활동내용","주요활동","프로그램내용")
    "목표" = @("목표","교육목표","운영목표","학습목표")
    "강사명" = @("강사명","강사","성명","담당강사","강사성명")
    "연락처" = @("연락처","전화번호","휴대전화","휴대폰")
    "준비물" = @("준비물","재료","준비사항")
    "기관명" = @("기관명","학교명","기관","소속기관")
}

function Canonical([string]$label) {
    $n = Normalize $label
    foreach ($key in $aliases.Keys) {
        foreach ($v in $aliases[$key]) {
            $nv = Normalize $v
            if ($n -eq $nv) { return $key }
        }
    }
    return $null
}

function Extract-Facts([string]$text) {
    $facts = @{}

    # 1) '항목: 값' 형식
    foreach ($line in ($text -split "`r?`n")) {
        if ($line -match '^\s*([^:：]{1,20})\s*[:：]\s*(.+?)\s*$') {
            $key = Canonical $matches[1]
            if ($key) { $facts[$key] = $matches[2].Trim() }
        }
    }

    # 2) 날짜는 대화 전체에서 가장 마지막 날짜 표현을 우선
    $dateMatches = [regex]::Matches($text, '(20\d{2})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일')
    if ($dateMatches.Count -gt 0) {
        $m = $dateMatches[$dateMatches.Count-1]
        $facts["일시"] = "{0}년 {1:D2}월 {2:D2}일" -f [int]$m.Groups[1].Value,[int]$m.Groups[2].Value,[int]$m.Groups[3].Value
    }

    # 3) 명시적 '대상은/대상:' 패턴
    $m = [regex]::Matches($text, '(?:대상은|대상은\s*|교육대상은|참여대상은)\s*([^\r\n,.]{2,30})')
    if ($m.Count -gt 0) { $facts["대상"] = $m[$m.Count-1].Groups[1].Value.Trim() }

    # 4) 인원
    $m = [regex]::Matches($text, '(?:인원은|인원\s*[:：]?|참여인원\s*[:：]?)\s*(\d{1,4})\s*명')
    if ($m.Count -gt 0) { $facts["인원"] = $m[$m.Count-1].Groups[1].Value.Trim() + "명" }

    # 5) 프로그램명/사업명 명시 패턴
    $m = [regex]::Matches($text, '(?:프로그램명|사업명|강의명|교육명)\s*(?:은|는|[:：])\s*([^\r\n,.]{2,60})')
    if ($m.Count -gt 0) { $facts["프로그램명"] = $m[$m.Count-1].Groups[1].Value.Trim() }

    return $facts
}

function Detect-Labels([string]$docText) {
    $labels = New-Object System.Collections.Generic.List[object]
    foreach ($key in $aliases.Keys) {
        foreach ($v in $aliases[$key]) {
            if ($docText -match [regex]::Escape($v)) {
                $labels.Add([pscustomobject]@{ Canonical=$key; Label=$v })
                break
            }
        }
    }
    return $labels
}

function Refresh-Proposals {
    $grid.Rows.Clear()
    $facts = Extract-Facts $txtConversation.Text
    $labels = Detect-Labels $script:DocText

    foreach ($item in $labels) {
        $val = ""
        if ($facts.ContainsKey($item.Canonical)) { $val = $facts[$item.Canonical] }
        $status = if ($val) { "입력 제안" } else { "확인 필요" }
        [void]$grid.Rows.Add($item.Label, $item.Canonical, $val, $status)
    }

    $lblStatus.Text = "문서 항목 $($labels.Count)개 감지 / 대화값 $($facts.Count)개 추출"
}

function Make-Output {
    if (-not (Test-Path $txtDoc.Text)) { throw "한글 문서를 선택하세요." }
    Refresh-Proposals

    $save = New-Object System.Windows.Forms.SaveFileDialog
    $save.Filter = "한글 문서 (*.hwp)|*.hwp|한글 XML 문서 (*.hwpx)|*.hwpx"
    $ext = [IO.Path]::GetExtension($txtDoc.Text)
    $save.FileName = ([IO.Path]::GetFileNameWithoutExtension($txtDoc.Text)) + "_자동작성" + $ext
    if ($save.ShowDialog() -ne "OK") { return }

    $args = New-Object System.Collections.Generic.List[string]
    $args.Add("edit")
    $args.Add($txtDoc.Text)
    $args.Add("-o")
    $args.Add($save.FileName)

    # 안전한 1차 방식:
    # 현재 문서에 동일한 라벨 뒤 기존값이 명확히 있는 경우만 교체.
    # 빈 표 셀 좌표는 문서별 구조가 달라 v1에서는 자동 확정하지 않음.
    $changes = 0
    foreach ($row in $grid.Rows) {
        if ($row.IsNewRow) { continue }
        $value = [string]$row.Cells[2].Value
        if ([string]::IsNullOrWhiteSpace($value)) { continue }

        $label = [string]$row.Cells[0].Value
        # 라벨 자체를 바꾸지 않도록, "라벨 + 뒤따르는 기존값"을 찾는 단순 패턴은 여기서 수행하지 않음.
        # 대신 문서 안 기존값과 정확히 일치하는 값이 사용자가 '기존값=>새값'으로 적은 경우 지원.
    }

    # 사용자가 수동 교체 지시를 별도 칸에 넣은 경우 처리
    foreach ($line in ($txtReplace.Text -split "`r?`n")) {
        if ($line -match '^\s*(.+?)\s*=>\s*(.+?)\s*$') {
            $args.Add("--replace")
            $args.Add($matches[1].Trim() + "=>" + $matches[2].Trim())
            $changes++
        }
    }

    if ($changes -eq 0) {
        [System.Windows.Forms.MessageBox]::Show(
            "문서 항목과 대화값 분석은 완료했습니다.`r`n`r`n하지만 이 1차 Windows 앱은 임의 HWP의 빈 표 셀 좌표를 100% 자동 확정하지 않습니다.`r`n현재는 아래 '정확 교체' 칸에 기존값=>새값이 있을 때만 안전하게 새 HWP를 만듭니다.",
            "1차 버전 안내","OK","Information"
        )
        return
    }

    $args.Add("--verify")
    [void](Run-Hwp $args.ToArray())
    [System.Windows.Forms.MessageBox]::Show("완성본을 만들었습니다.`r`n$($save.FileName)","완료","OK","Information")
}

$form = New-Object System.Windows.Forms.Form
$form.Text = "한글문서 자동작성 1"
$form.Size = New-Object System.Drawing.Size(1000,760)
$form.StartPosition = "CenterScreen"
$form.Font = New-Object System.Drawing.Font("맑은 고딕",10)

$lblTitle = New-Object System.Windows.Forms.Label
$lblTitle.Text = "한글문서 자동작성"
$lblTitle.Font = New-Object System.Drawing.Font("맑은 고딕",18,[Drawing.FontStyle]::Bold)
$lblTitle.AutoSize = $true
$lblTitle.Location = New-Object Drawing.Point(25,18)
$form.Controls.Add($lblTitle)

$lblSub = New-Object System.Windows.Forms.Label
$lblSub.Text = "HWP/HWPX 문서를 읽고 대화내용에서 필요한 값을 찾아 자동작성 제안을 만듭니다."
$lblSub.AutoSize = $true
$lblSub.Location = New-Object Drawing.Point(28,58)
$form.Controls.Add($lblSub)

# hwp.exe
$lab = New-Object System.Windows.Forms.Label
$lab.Text="hwp.exe"; $lab.Location=New-Object Drawing.Point(28,95); $lab.AutoSize=$true
$form.Controls.Add($lab)
$txtHwpExe = New-Object System.Windows.Forms.TextBox
$txtHwpExe.Location=New-Object Drawing.Point(110,90); $txtHwpExe.Width=720
$form.Controls.Add($txtHwpExe)
$btnHwp = New-Object System.Windows.Forms.Button
$btnHwp.Text="찾기"; $btnHwp.Location=New-Object Drawing.Point(845,88)
$form.Controls.Add($btnHwp)

# doc
$lab2 = New-Object System.Windows.Forms.Label
$lab2.Text="한글문서"; $lab2.Location=New-Object Drawing.Point(28,135); $lab2.AutoSize=$true
$form.Controls.Add($lab2)
$txtDoc = New-Object System.Windows.Forms.TextBox
$txtDoc.Location=New-Object Drawing.Point(110,130); $txtDoc.Width=720
$form.Controls.Add($txtDoc)
$btnDoc = New-Object System.Windows.Forms.Button
$btnDoc.Text="선택"; $btnDoc.Location=New-Object Drawing.Point(845,128)
$form.Controls.Add($btnDoc)

$grpConv = New-Object System.Windows.Forms.GroupBox
$grpConv.Text="AI와 나눈 대화내용"; $grpConv.Location=New-Object Drawing.Point(25,175); $grpConv.Size=New-Object Drawing.Size(930,190)
$form.Controls.Add($grpConv)
$txtConversation = New-Object System.Windows.Forms.TextBox
$txtConversation.Multiline=$true; $txtConversation.ScrollBars="Vertical"
$txtConversation.Location=New-Object Drawing.Point(15,28); $txtConversation.Size=New-Object Drawing.Size(900,145)
$grpConv.Controls.Add($txtConversation)

$btnAnalyze = New-Object System.Windows.Forms.Button
$btnAnalyze.Text="문서 분석 + 자동 매칭"
$btnAnalyze.Location=New-Object Drawing.Point(25,380); $btnAnalyze.Size=New-Object Drawing.Size(190,36)
$form.Controls.Add($btnAnalyze)

$lblStatus = New-Object System.Windows.Forms.Label
$lblStatus.Text="문서를 선택한 뒤 분석하세요."
$lblStatus.Location=New-Object Drawing.Point(230,390); $lblStatus.AutoSize=$true
$form.Controls.Add($lblStatus)

$grid = New-Object System.Windows.Forms.DataGridView
$grid.Location=New-Object Drawing.Point(25,430); $grid.Size=New-Object Drawing.Size(930,155)
$grid.AllowUserToAddRows=$false; $grid.AutoSizeColumnsMode="Fill"
[void]$grid.Columns.Add("문서표현","문서 항목")
[void]$grid.Columns.Add("의미","의미")
[void]$grid.Columns.Add("값","대화에서 찾은 값")
[void]$grid.Columns.Add("상태","상태")
$form.Controls.Add($grid)

$grpReplace = New-Object System.Windows.Forms.GroupBox
$grpReplace.Text="정확 교체(1차 버전 안전모드) — 한 줄에 기존값=>새값"; $grpReplace.Location=New-Object Drawing.Point(25,595); $grpReplace.Size=New-Object Drawing.Size(720,90)
$form.Controls.Add($grpReplace)
$txtReplace = New-Object System.Windows.Forms.TextBox
$txtReplace.Multiline=$true; $txtReplace.ScrollBars="Vertical"
$txtReplace.Location=New-Object Drawing.Point(15,25); $txtReplace.Size=New-Object Drawing.Size(690,50)
$grpReplace.Controls.Add($txtReplace)

$btnMake = New-Object System.Windows.Forms.Button
$btnMake.Text="완성 HWP 만들기"
$btnMake.Location=New-Object Drawing.Point(765,610); $btnMake.Size=New-Object Drawing.Size(190,55)
$form.Controls.Add($btnMake)

$settings = Load-Settings
if ($settings.hwpExe) { $txtHwpExe.Text = $settings.hwpExe }

$btnHwp.Add_Click({
    $dlg=New-Object System.Windows.Forms.OpenFileDialog
    $dlg.Filter="hwp.exe|hwp.exe|실행파일 (*.exe)|*.exe"
    if ($dlg.ShowDialog() -eq "OK") {
        $txtHwpExe.Text=$dlg.FileName
        Save-Settings $dlg.FileName
    }
})

$btnDoc.Add_Click({
    $dlg=New-Object System.Windows.Forms.OpenFileDialog
    $dlg.Filter="한글 문서 (*.hwp;*.hwpx)|*.hwp;*.hwpx"
    if ($dlg.ShowDialog() -eq "OK") {
        $txtDoc.Text=$dlg.FileName
        try {
            $script:DocText = Run-Hwp @("cat",$dlg.FileName)
            $lblStatus.Text="문서를 읽었습니다. 대화내용을 붙여넣고 자동 매칭을 누르세요."
        } catch {
            [System.Windows.Forms.MessageBox]::Show($_.Exception.Message,"오류","OK","Error")
        }
    }
})

$btnAnalyze.Add_Click({
    try {
        if (-not $script:DocText) {
            if (-not (Test-Path $txtDoc.Text)) { throw "한글 문서를 먼저 선택하세요." }
            $script:DocText = Run-Hwp @("cat",$txtDoc.Text)
        }
        Refresh-Proposals
    } catch {
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message,"오류","OK","Error")
    }
})

$btnMake.Add_Click({
    try { Make-Output } catch {
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message,"오류","OK","Error")
    }
})

[void]$form.ShowDialog()
