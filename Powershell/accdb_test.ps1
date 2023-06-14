$adOpenStatic = 3
$adLockOptimistic = 3

$objConnection = New-Object -com 'ADODB.Connection'
$objRecordSet = New-Object -com 'ADODB.Recordset'

$objConnection.Open('Provider = Microsoft.ACE.OLEDB.12.0; Data Source = "C:\Users\MW116637\Documents\Database1.accdb"')

$objRecordset.Open('Select * From Animal', $objConnection, $adOpenStatic, $adLockOptimistic)

$objRecordSet.AddNew()
$objRecordSet.Fields.Item('AnimalID').Value = '202'
$objRecordSet.Fields.Item('Name').Value = 'Test'
$objRecordSet.Update()

$objRecordSet.Close()
$objConnection.Close()
