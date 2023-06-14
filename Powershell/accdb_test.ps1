$adOpenStatic = 3
$adLockOptimistic = 3

$objConnection = New-Object -com 'ADODB.Connection'
$objRecordSet = New-Object -com 'ADODB.Recordset'

$objConnection.Open('Provider = Microsoft.ACE.OLEDB.12.0; Data Source = "C:\Users\MW116637\Documents\Database1.accdb"')

$searchUser = 'Test'  # Specify the user you want to search for
$searchID = '202'     # Specify the ID you want to search for

# Open the recordset and search for User and ID
$objRecordset.Open("SELECT * FROM Table1 WHERE User = '$searchUser' OR ID = '$searchID'", $objConnection, $adOpenStatic, $adLockOptimistic)

if ($objRecordSet.EOF)
{
    # User and ID not found
    $maxUID = 0

    # Find the highest existing UID less than 6000
    $objRecordset.Open('SELECT MAX(CAST(UID AS Int)) AS MaxUID FROM Table1 WHERE CAST(UID AS Int) < 6000', $objConnection, $adOpenStatic, $adLockOptimistic)
    if (-not $objRecordset.EOF)
    {
        $maxUID = [int]$objRecordset.Fields.Item('MaxUID').Value
    }
    $objRecordset.Close()

    if ($maxUID -ge 5999)
    {
        # Maximum capacity reached, display error
        Write-Host "Error: Maximum capacity of users reached (UID: $maxUID)"
    }
    else
    {
        # Increment the highest UID and add the new user
        $newUID = $maxUID + 1
        $objRecordSet.AddNew()
        $objRecordSet.Fields.Item('ID').Value = $searchID
        $objRecordSet.Fields.Item('User').Value = $searchUser
        $objRecordSet.Fields.Item('UID').Value = $newUID
        $objRecordSet.Update()

        Write-Host "User added with ID: $searchID, User: $searchUser, and incremented UID: $newUID"
    }
}
else
{
    # User and ID found, display the matching record(s)
    while (-not $objRecordSet.EOF)
    {
        $id = $objRecordSet.Fields.Item('ID').Value
        $user = $objRecordSet.Fields.Item('User').Value
        $uid = $objRecordSet.Fields.Item('UID').Value
        Write-Host "ID: $id, User: $user, UID: $uid"
        $objRecordSet.MoveNext()
    }
}

$objRecordSet.Close()
$objConnection.Close()
