<#
TODO:

script has issues when adding corp users to other domains. Script works fine in corp.int domain
need to be able to iterate through more than one name
need to be able to provide credentials from one domain into an AD group in another domain
need to be able to provide credentials dependent on domain of AD group
need to be able to iterate through multiple shares spread across different domains

Exceptions to think through:

some AD groups have no single users but other sub groups
some AD groups have single users and other sub groups
some directories have no AD groups only single users
some directories are unix instead of NTFS
some users request readWrite permissions, but the AD group being used by single users is fullControl

check group type
if domain local group user must be in local domain
#>

Import-Module ActiveDirectory

$taskNumber = Read-Host -Prompt 'Input the SCTask number'
$givenNames = Read-Host -Prompt 'Input the user given name (If more than one, separate by ";")'
$userDomain = Read-Host -Prompt 'Provide domain of user (ex. corp.int)'  # domain of share location, requires a certain level of knowledge not easily obtained from script
$permissionsType = Read-Host -Prompt "`n1. readWrite `n2. readOnly `n3. fullControl `n`nPlease select permission type (give number)"    # would like to have newlines for each option
$shareLocation = Read-Host -Prompt 'Provide share location to update permissions' # requires full path to desired directory
$fqdn = [System.Net.Dns]::GetHostEntry($shareLocation.split('\')[2]).HostName
$serverShort = $fqdn.Split('.')[0]
$shareDomain = $fqdn.Replace("$serverShort.", '')
$shareLocation = $shareLocation.Replace($shareLocation.split('\')[2], $fqdn)
$credentials = Read-Host -Prompt 'Provide your credentials'   # personal credentials needed to add user to group

$usrName = Get-ADUser -Filter "Name -eq '$($givenNames)'" -Server $userDomain | Select-Object -ExpandProperty SamAccountName

Write-Host
Write-Host "The username for $($givenNames) is: $($usrName)"
Write-Host

Write-Host
Write-Host '***************'
Write-Host "The current permissions for $($usrName) in $($userDomain) are: "
Write-Host '***************'
Write-Host

Get-ADUser -Filter "samaccountname -eq '$($usrName)'" -Properties MemberOf -Server $userDomain | Select-Object -ExpandProperty MemberOf | Sort-Object | Format-Table -AutoSize

Write-Host
Write-Host '***************'
Write-Host "The current permissions for '$($shareLocation)' is: "
Write-Host '***************'
Write-Host

if ("$($permissionsType)" -eq '1')
{
    Get-Acl $shareLocation | Select-Object -ExpandProperty access | Where-Object { $_.FileSystemRights -like 'Modify*' } | Format-Table -AutoSize
}
if ("$($permissionsType)" -eq '2')
{
    Get-Acl $shareLocation | Select-Object -ExpandProperty access | Where-Object { $_.FileSystemRights -like 'ReadAndExecute*' } | Format-Table -AutoSize
}
if ("$($permissionsType)" -eq '3')
{
    Get-Acl $shareLocation | Select-Object -ExpandProperty access | Where-Object { $_.FileSystemRights -like 'FullControl*' } | Format-Table -AutoSize
}

$adGroup = Read-Host -Prompt 'Input the desired AD group'  # choice is somewhat arbitrary as long as its the correct permission type. Would prefer to reduce available groups to one per permission type
$groupDomain = Read-Host -Prompt 'Provide domain of AD group (ex. corp.int)'  # domain of share location, requires a certain level of knowledge not easily obtained from script
$date = Get-Date    # mostly used for documenting when permission requests were fulfilled

Write-Host "You input AD group: '$($adGroup)' on '$($date)'" 

Write-Host
Write-Host '***************'
Write-Host "Active Directory group selected for permissions modification of share $($shareLocation) is: '$($adGroup)' in '$($domain)' domain."
Write-Host '***************'
Write-Host

Get-ADGroup -Identity $adGroup -Server $groupDomain

Write-Host
Write-Host '***************'
Write-Host "$($adGroup) current membership:"
Write-Host '***************'
Write-Host

Get-ADGroupMember $adGroup -Server $groupDomain | Sort-Object Name | Format-Table -AutoSize

Write-Host
Write-Host '***************'
Write-Host "Adding permissions for $($givenNames) in $($adGroup) of share $($shareLocation): "
Write-Host '***************'
Write-Host

Add-ADGroupMember -Identity $adGroup -Server $groupDomain -Members $addUser -Credential $credentials

Write-Host
Write-Host '***************'
Write-Host "Validating $($adGroup) membership:"
Write-Host '***************'
Write-Host

Get-ADGroupMember $adGroup -Server $groupDomain | Sort-Object Name | Format-Table -AutoSize

Write-Host
Write-Host '***************'
Write-Host "'$($taskNumber)' completed on '$($date)' by '$($credentials)'" 
Write-Host '***************'
Write-Host
