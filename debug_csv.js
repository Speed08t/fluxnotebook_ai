// Debug script for CSV import functionality
// Run this in browser console to test CSV import

console.log('=== CSV Import Debug Script ===');

// Check if elements exist
const elements = {
    csvFileInput: document.getElementById('csv-file-input'),
    importCsvBtn: document.getElementById('import-csv-btn'),
    showDatasetsBtn: document.getElementById('show-datasets-btn'),
    datasetModal: document.getElementById('dataset-modal'),
    jupyterTab: document.getElementById('jupyter-tab'),
    jupyterContent: document.getElementById('jupyter-content'),
    cellsContainer: document.getElementById('cells-container')
};

console.log('Element check:', elements);

// Check if functions exist
const functions = {
    setupCSVImport: typeof setupCSVImport !== 'undefined',
    importCSVFile: typeof importCSVFile !== 'undefined',
    updateDatasetList: typeof updateDatasetList !== 'undefined',
    pyodideReady: typeof pyodideReady !== 'undefined' ? pyodideReady : 'undefined'
};

console.log('Function check:', functions);

// Check if variables exist
const variables = {
    importedDatasets: typeof importedDatasets !== 'undefined' ? importedDatasets.size : 'undefined',
    pyodide: typeof pyodide !== 'undefined' ? 'exists' : 'undefined'
};

console.log('Variable check:', variables);

// Test button click simulation
function testImportButton() {
    console.log('Testing import button...');
    const btn = document.getElementById('import-csv-btn');
    if (btn) {
        btn.click();
        console.log('Import button clicked');
    } else {
        console.error('Import button not found');
    }
}

function testDatasetsButton() {
    console.log('Testing datasets button...');
    const btn = document.getElementById('show-datasets-btn');
    if (btn) {
        btn.click();
        console.log('Datasets button clicked');
    } else {
        console.error('Datasets button not found');
    }
}

// Test CSV creation and import
function testCSVImport() {
    console.log('Testing CSV import with sample data...');
    
    // Create a sample CSV file
    const csvContent = `name,age,city
John,25,New York
Jane,30,Los Angeles
Bob,35,Chicago`;
    
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const file = new File([blob], 'test_data.csv', { type: 'text/csv' });
    
    console.log('Created test file:', file);
    
    if (typeof importCSVFile !== 'undefined') {
        importCSVFile(file).then(() => {
            console.log('CSV import completed');
        }).catch(error => {
            console.error('CSV import failed:', error);
        });
    } else {
        console.error('importCSVFile function not available');
    }
}

// Export functions for manual testing
window.debugCSV = {
    testImportButton,
    testDatasetsButton,
    testCSVImport,
    elements,
    functions,
    variables
};

console.log('Debug functions available as window.debugCSV');
console.log('Try: debugCSV.testImportButton() or debugCSV.testCSVImport()');
